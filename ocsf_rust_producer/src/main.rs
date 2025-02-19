use reqwest::Client;
use serde_json::{json, Value};
use std::error::Error;
use chrono::Utc;
use rand::{thread_rng, Rng};

fn generate_random_ip() -> String {
    let mut rng = thread_rng();
    format!(
        "{}.{}.{}.{}",
        rng.gen_range(1..255),
        rng.gen_range(0..255),
        rng.gen_range(0..255),
        rng.gen_range(1..255)
    )
}

async fn send_network_activity(client: &Client, event: &Value) -> Result<(), Box<dyn Error>> {
    // Use the alias name directly for consistent indexing
    let opensearch_url = "https://52.66.102.200:9200/ocsf-1.1.0-4001-network_activity/_doc";
    
    let response = client
        .post(opensearch_url)
        .basic_auth("admin", Some("Anubhav@321"))
        .header("Content-Type", "application/json")
        .json(&event)
        .send()
        .await?;

    println!("Status: {}", response.status());
    if !response.status().is_success() {
        println!("Response: {}", response.text().await?);
    }
    Ok(())
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn Error>> {
    let client = Client::builder()
        .danger_accept_invalid_certs(true)
        .build()?;

    let timestamp = Utc::now();
    let timestamp_str = timestamp.to_rfc3339();
    let epoch_seconds = timestamp.timestamp();
    
    let event = json!({
        // Base Event Fields
        "activity_id": 1,
        "activity_name": "Traffic",
        "category_name": "Network Activity",
        "category_uid": 4,
        "class_name": "Network Activity",
        "class_uid": 4001,
        "time": epoch_seconds,
        "@timestamp": timestamp_str,  // Add @timestamp field
        "type_name": "Network Traffic",
        "type_uid": 400101,
        
        // Network Activity Specific Fields
        "action": "ALLOW",
        "action_id": 1,
        "app_name": "Web Browser",
        "disposition": "Allowed",
        "disposition_id": 1,

        // Connection Info
        "connection_info": {
            "direction": "Outbound",
            "direction_id": 2,
            "protocol_name": "TCP",
            "protocol_num": 6,
            "boundary": "Internet Gateway",
            "boundary_id": 1
        },

        // Source Endpoint
        "src_endpoint": {
            "hostname": "client-workstation",
            "ip": generate_random_ip(),
            "port": thread_rng().gen_range(49152..65535),
            "svc_name": "web-client",
            "type": "Workstation",
            "type_id": 1
        },

        // Destination Endpoint
        "dst_endpoint": {
            "hostname": "web-server.example.com",
            "ip": generate_random_ip(),
            "port": 443,
            "svc_name": "https",
            "type": "Server",
            "type_id": 2
        },

        // TLS Information
        "tls": {
            "version": "1.3",
            "cipher": "TLS_AES_256_GCM_SHA384",
            "sni": "web-server.example.com"
        },

        // Traffic Information
        "traffic": {
            "bytes_in": thread_rng().gen_range(1000..5000),
            "bytes_out": thread_rng().gen_range(500..2000),
            "packets_in": thread_rng().gen_range(10..50),
            "packets_out": thread_rng().gen_range(5..20)
        },

        // Metadata
        "metadata": {
            "version": "1.1.0",
            "product": {
                "name": "OCSF Network Monitor",
                "vendor_name": "Demo Vendor",
                "version": "1.0.0",
                "feature": {
                    "name": "Network Monitoring",
                    "uid": "NM001"
                }
            },
            "profiles": ["network", "security"],
            "original_time": timestamp_str,
            "time": epoch_seconds  // Add time field in metadata
        },

        // Additional Fields
        "severity": "Informational",
        "severity_id": 1,
        "status": "Success",
        "status_id": 1,
        "message": "Network traffic detected and allowed"
    });

    match send_network_activity(&client, &event).await {
        Ok(_) => println!("Successfully sent network activity event"),
        Err(e) => eprintln!("Error sending event: {}", e),
    }

    Ok(())
}
