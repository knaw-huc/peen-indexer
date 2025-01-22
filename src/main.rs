use annorepo_client::AnnoRepoClient;
use reqwest::header::HeaderMap;
use reqwest::ClientBuilder;
use serde_json_path::JsonPath;
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

    let annoclient = AnnoRepoClient::new(ANNOREPO_BASE, ANNOREPO_CONTAINER).unwrap();

    match annoclient.get_about().await {
        Ok(text) => println!("text: {:?}", text),
        Err(err) => println!("err: {:?}", err),
    }

    let fields = annoclient.get_fields().await?;
    println!("fields: {:?}", fields);

    let indexes = annoclient.get_indexes().await?;
    println!("\nindexes: {:?}", indexes);
    Ok(())
}
