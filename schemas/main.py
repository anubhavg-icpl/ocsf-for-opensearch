#!/usr/bin/env python3

# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"),
# to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense,
# and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so.
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
# IN THE SOFTWARE.

# Before running the script:
# Change the variables in the Initialise variables section to match your cluster details
# Upload the component_templates.zip and index_templates.zip to an S3 bucket and update the variables in the Initialise variables section

import os
import json
import zipfile
from opensearchpy import OpenSearch, RequestsHttpConnection
from datetime import datetime
import urllib3
urllib3.disable_warnings()

## Local paths configuration
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
COMPONENT_TEMPLATES_DIR = os.path.join(BASE_DIR, 'templates', 'component_templates')
INDEX_TEMPLATES_DIR = os.path.join(BASE_DIR, 'templates', 'index_templates')

## OpenSearch configuration
OS_HOST = '52.66.102.200'  # Your OpenSearch host
OS_PORT = 9200
OS_USERNAME = 'admin'
OS_PASSWORD = 'Anubhav@321'

def authenticate_local():
    """Authenticate with OpenSearch instance"""
    try:
        client = OpenSearch(
            hosts=[{'host': OS_HOST, 'port': OS_PORT}],
            http_auth=(OS_USERNAME, OS_PASSWORD),
            use_ssl=True,  # Enable SSL
            verify_certs=False,  # Don't verify SSL certs
            ssl_show_warn=False,  # Don't show SSL warnings
            connection_class=RequestsHttpConnection,
            timeout=30
        )
        info = client.info()
        print(f"Successfully connected to: {info['version']['distribution']}: {info['version']['number']}")
        return client
    except Exception as e:
        print(f"Connection failed: {str(e)}")
        print(f"Please verify:\n1. OpenSearch is running at {OS_HOST}:{OS_PORT}\n2. Credentials are correct\n3. Network/firewall allows connection")
        raise

def ensure_directories():
    """Create necessary directories if they don't exist"""
    os.makedirs(COMPONENT_TEMPLATES_DIR, exist_ok=True)
    os.makedirs(INDEX_TEMPLATES_DIR, exist_ok=True)
    print(f"Directories created/verified at: {BASE_DIR}")

def ISM_INIT(client):
    try:
        # Delete existing policy if it exists
        try:
            client.plugins.index_management.delete_policy(policy_id="rollover-expiration-policy")
        except:
            pass
        
        # Create new policy
        ism_policy = {
            "policy": {
                "policy_id": "rollover-expiration-policy",
                "description": "This policy rollsover the index daily or if it reaches 40gb. It also expires logs older than 15 days",
                "default_state": "rollover",
                "states": [
                    {
                        "name": "rollover",
                        "actions": [
                            {
                                "retry": {
                                    "count": 3,
                                    "backoff": "exponential",
                                    "delay": "1h"
                                },
                                "rollover": {
                                    "min_size": "40gb",
                                    "min_index_age": "1d",
                                    "copy_alias": False
                                }
                            }
                        ],
                        "transitions": [
                            {
                                "state_name": "hot"
                            }
                        ]
                    },
                    {
                        "name": "hot",
                        "actions": [],
                        "transitions": [
                            {
                                "state_name": "delete",
                                "conditions": {
                                    "min_index_age": "15d"
                                }
                            }
                        ]
                    },
                    {
                        "name": "delete",
                        "actions": [
                            {
                                "timeout": "5h",
                                "retry": {
                                    "count": 3,
                                    "backoff": "exponential",
                                    "delay": "1h"
                                },
                                "delete": {}
                            }
                        ],
                        "transitions": []
                    }
                ],
                "ism_template": [
                    {
                        "index_patterns": [
                            "ocsf-*"
                        ],
                        "priority": 9
                    }
                ]
            }
        }
        try:
            client.plugins.index_management.put_policy(policy = "rollover-expiration-policy", body=ism_policy)
            print ("ISM Policy created")
        except Exception as e:
            print(f"Error creating ISM Policy: {e}")
            pass
    except Exception as e:
        print(f"Error creating ISM Policy: {e}")
        pass

def alias_init(client):
    index_date = datetime.now().strftime("%Y.%m.%d")
    index_list = [
        "ocsf-1.1.0-2002-vulnerability_finding",
        "ocsf-1.1.0-2003-compliance_finding",
        "ocsf-1.1.0-2004-detection_finding",
        "ocsf-1.1.0-3001-account_change",
        "ocsf-1.1.0-3002-authentication",
        "ocsf-1.1.0-4001-network_activity",
        "ocsf-1.1.0-4002-http_activity",
        "ocsf-1.1.0-4003-dns_activity",
        "ocsf-1.1.0-6003-api_activity",
    ]
    
    # Default index settings
    default_settings = {
        "settings": {
            "index": {
                "max_docvalue_fields_search": 500,
                "mapping.total_fields.limit": 4000,
                "number_of_shards": 1,
                "number_of_replicas": 1,
                "plugins": {
                    "index_state_management": {
                        "rollover_alias": None  # Will be set per index
                    }
                }
            }
        },
        "mappings": {
            "dynamic": "true",
            "date_detection": True,
            "dynamic_date_formats": ["strict_date_optional_time||epoch_second"],
            "dynamic_templates": [
                {
                    "strings_as_keywords": {
                        "match_mapping_type": "string",
                        "mapping": {
                            "type": "keyword",
                            "ignore_above": 1024
                        }
                    }
                }
            ],
            "properties": {
                "time": {
                    "type": "date",
                    "format": "strict_date_optional_time||epoch_second"
                },
                "@timestamp": {
                    "type": "date",
                    "format": "strict_date_optional_time||epoch_second"
                }
            }
        }
    }

    for index in index_list:
        try:
            # Update settings for this specific index
            settings = default_settings.copy()
            settings["settings"]["index"]["plugins"]["index_state_management"]["rollover_alias"] = index
            
            index_name = f"<{index}-{{now/d}}-000000>"
            client.indices.create(index=index_name, body=settings)
            print(f"Created index {index} with updated settings")
            
            # Create alias
            alias_name = index
            alias_index = f"{index}-*"
            client.indices.put_alias(index=alias_index, name=alias_name)
            print(f"Created alias {alias_name}")
            
        except Exception as e:
            print(f"Error handling index {index}: {e}")
            continue

def install_component_templates(client):
    for root, dirs, files in os.walk(COMPONENT_TEMPLATES_DIR):
        for file in files:
            if file.endswith('_body.json'):
                file_path = os.path.join(root, file)
                template_name = os.path.splitext(file)[0][:-5]

                with open(file_path, 'r') as f:
                    template_content = json.load(f)

                    try:
                        response = client.cluster.put_component_template(
                            name=template_name, 
                            body=template_content
                        )
                        if response['acknowledged']:
                            print(f'Created component template: {template_name}')
                        else:
                            print(f'Error creating component template: {template_name}')
                    except Exception as e:
                        print(f'Error creating component template: {template_name} - {e}')

def install_index_templates(client):
    for root, dirs, files in os.walk(INDEX_TEMPLATES_DIR):
        for file in files:
            if file.endswith('_body.json'):
                file_path = os.path.join(root, file)
                template_name = os.path.splitext(file)[0][:-5]

                with open(file_path, 'r') as f:
                    template_content = json.load(f)

                    try:
                        response = client.indices.put_index_template(
                            name=template_name, 
                            body=template_content
                        )
                        if response['acknowledged']:
                            print(f'Created index template: {template_name}')
                        else:
                            print(f'Error creating index template: {template_name}')
                    except Exception as e:
                        print(f'Error creating index template: {template_name} - {e}')

def main():
    try:
        ensure_directories()
        client = authenticate_local()
        install_component_templates(client)
        install_index_templates(client)
        ISM_INIT(client)
        alias_init(client)
        print("Setup completed successfully!")
    except Exception as e:
        print(f"Setup failed: {str(e)}")
        raise

if __name__ == "__main__":
    main()