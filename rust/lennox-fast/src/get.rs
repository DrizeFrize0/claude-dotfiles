//! `lennox-fast get section.key`: reads one setting without starting Python.
//! Plain text, whole numbers and true/false are answered here; anything else
//! (a missing key that needs its default, decimals, lists) goes to the Python code.

use crate::{dir, python};
use serde_json::Value;
use std::fs;

pub fn run(args: &[String]) {
    let Some(key) = args.first() else {
        eprintln!("usage: lennox-get section.key");
        std::process::exit(2);
    };
    if let Some(text) = lookup(key) {
        println!("{text}");
        return;
    }
    python("lennox.getcli", args);
}

fn lookup(key: &str) -> Option<String> {
    let file = dir("XDG_CONFIG_HOME", ".config").join("lennox/settings.json");
    let root: Value = serde_json::from_str(&fs::read_to_string(file).ok()?).ok()?;
    let mut node = &root;
    for part in key.split('.') {
        node = node.get(part)?;
    }
    match node {
        Value::String(s) => Some(s.clone()),
        Value::Bool(b) => Some(b.to_string()),
        Value::Number(n) if n.is_i64() || n.is_u64() => Some(n.to_string()),
        _ => None,
    }
}
