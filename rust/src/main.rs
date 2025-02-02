use annorepo_client::AnnoRepoClient;
use reqwest::header::HeaderMap;
use reqwest::ClientBuilder;
use serde_json::Value;
use serde_json::Value::{Array, Bool};
use serde_json_path::JsonPath;
use std::collections::HashMap;
use std::error::Error;

const ANNOREPO_BASE: &'static str = "https://annorepo.suriano.huygens.knaw.nl";
const ANNOREPO_CONTAINER: &'static str = "suriano-1.0.1e-029";

#[tokio::main]
async fn main() -> Result<(), Box<dyn Error>> {
    let ar_services_url = format!("{}/services/{}", ANNOREPO_BASE, ANNOREPO_CONTAINER);
    let ar_metadata_url = format!("{}/metadata", ar_services_url);

    let url = reqwest::Url::parse(&ar_metadata_url).unwrap();
    println!("{}", url);

    let mut headers = HeaderMap::new();
    headers.insert("user-agent", "Brinta/1.0".parse().unwrap());

    let client = ClientBuilder::new().build().unwrap();
    let response = client.get(url).headers(headers.clone()).send().await?;

    let text = response.text().await?;
    println!("reponse.text: {}", text);

    // https://stackoverflow.com/questions/74974194/how-to-convert-a-string-to-a-valid-json-in-rust
    let json = serde_json::from_str(&text).unwrap();
    println!("response.json: {}", json);

    // let json: HashMap<String, Value> = response.json().await?;
    // println!("response: {:?}", &json);
    // println!("{}", serde_json::to_string_pretty(&json).unwrap());

    let path = JsonPath::parse("$.label")?;
    let label = path.query(&json).exactly_one()?;
    println!("{} -> {}", path, label);

    let client = AnnoRepoClient::new(ANNOREPO_BASE, ANNOREPO_CONTAINER).unwrap();

    let about = client.get_about().await?;
    println!("about: {:?}", about);
    println!("auth: {}", about["withAuthentication"]);
    if let Bool(b) = about["withAuthentication"] {
        println!("bool: {}", b);
    }
    // let p = JsonPath::parse("$.appName")?;
    // let l = p.query(&about).exactly_one()?;
    // println!("appName: {} ?== {}", l, about.get("appName").unwrap());
    // assert_eq!(l, &about["appName"]);
    // assert_eq!(&about["appName"], about.get("appName").unwrap());

    if let Array(dates) = client.get_distinct_values("body.metadata.date").await? {
        println!("distinct body.metadata.date count: {}", dates.len());
    }

    let body_types = client.get_distinct_values("body.type").await?;
    println!("distinct body.types: {:?}", body_types);

    // let fields = client.get_fields().await?;
    // let keys = fields.as_object().unwrap().keys();
    // keys.for_each(|f| println!("field: {}", f));

    let indexes = client.get_indexes().await?;
    println!("\nindexes: {:?}", indexes);

    let query = HashMap::from([("body.type", "LetterBody")]);
    let search_info = client.create_search(query).await?;
    let search_id = search_info.search_id();
    println!(
        "main: location={:?}, search_id={}",
        search_info.location(),
        &search_id
    );

    let info = client
        .read_search_info(&ANNOREPO_CONTAINER, &search_id)
        .await?;
    println!("info: {}", info);

    let json = client
        .read_search_result_page(&ANNOREPO_CONTAINER, &search_id, None)
        .await?;
    println!("json: {}", json);

    client
        .foreach_search_result_annotation(&ANNOREPO_CONTAINER, &search_id, None, &handle_anno)
        .await?;

    Ok(())
}

fn handle_anno(anno: &Value) {
    println!("handle_anno: {}", anno);
}
