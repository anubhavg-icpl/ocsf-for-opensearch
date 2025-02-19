use chrono::Utc;
use reqwest::Client;
use serde::{Deserialize, Serialize};
use std::error::Error;

// Define a sample OCSF event structure.
#[derive(Serialize, Deserialize, Debug)]
struct OcsfEvent {
    event_version: String,
    event_type: String,
    timestamp: String,
    source: String,
    // Additional fields can be added to match the OCSF schema.
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn Error>> {
    // Create a sample OCSF event.
    let event = OcsfEvent {
        event_version: "1.1.0".to_string(),
        event_type: "OCSF 3002 - Authentication".to_string(),
        timestamp: Utc::now().to_rfc3339(),
        source: "rust-sample".to_string(),
    };

    // Convert the event to a JSON string.
    let event_json = serde_json::to_string(&event)?;
    println!("Generated event: {}", event_json);

    // Define your OpenSearch endpoint (update as needed).
    let opensearch_url = "http://localhost:9200/ocsf-events/_doc/";

    // Create an HTTP client.
    let client = Client::new();

    // Send the event to OpenSearch with Basic Authentication.
    let response = client
        .post(opensearch_url)
        .basic_auth("admin", Some("Anubhav@321"))
        .header("Content-Type", "application/json")
        .body(event_json)
        .send()
        .await?;

    // Print the response from OpenSearch.
    let resp_text = response.text().await?;
    println!("Response from OpenSearch: {}", resp_text);

    Ok(())
}
