//! What you type in the address bar: an address or a search.

pub const SEARCH: &str = "https://duckduckgo.com/?q=";

/// Turns what was typed into the address to load. Plain `http://` is upgraded to https.
pub fn resolve(input: &str) -> String {
    let t = input.trim();
    if t.is_empty() {
        return "about:blank".into();
    }
    if let Some(rest) = t.strip_prefix("http://") {
        if !is_local(rest) {
            return format!("https://{rest}");
        }
        return t.to_string();
    }
    for scheme in ["https://", "file://", "about:", "lennox:"] {
        if t.starts_with(scheme) {
            return t.to_string();
        }
    }
    let host = t.split(['/', '?', '#']).next().unwrap_or("");
    let looks_like_address = !t.contains(' ')
        && (host.contains('.') || host.starts_with("localhost") || host.parse::<std::net::IpAddr>().is_ok() || host.contains(':'));
    if looks_like_address {
        return if is_local(t) { format!("http://{t}") } else { format!("https://{t}") };
    }
    format!("{SEARCH}{}", encode(t))
}

/// Home and lab addresses (the Pi hub) have no https: keep http for them.
fn is_local(rest: &str) -> bool {
    let host = rest.split(['/', '?', '#']).next().unwrap_or("");
    let name = host.rsplit_once(':').map(|(h, _)| h).unwrap_or(host);
    name == "localhost"
        || name.ends_with(".local")
        || name.ends_with(".ts.net")
        || name.parse::<std::net::Ipv4Addr>().map(|ip| ip.is_private() || ip.is_loopback() || ip.octets()[0] == 100).unwrap_or(false)
}

pub fn encode(text: &str) -> String {
    let mut out = String::new();
    for b in text.bytes() {
        match b {
            b'A'..=b'Z' | b'a'..=b'z' | b'0'..=b'9' | b'-' | b'_' | b'.' | b'~' => out.push(b as char),
            b' ' => out.push('+'),
            _ => out.push_str(&format!("%{b:02X}")),
        }
    }
    out
}

pub fn host_of(url: &str) -> Option<String> {
    let rest = url.split_once("://")?.1;
    let host = rest.split(['/', '?', '#']).next()?;
    let host = host.rsplit_once('@').map(|(_, h)| h).unwrap_or(host);
    Some(host.rsplit_once(':').map(|(h, _)| h).unwrap_or(host).to_ascii_lowercase())
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn typed_text() {
        assert_eq!(resolve("rust lang"), "https://duckduckgo.com/?q=rust+lang");
        assert_eq!(resolve("example.com"), "https://example.com");
        assert_eq!(resolve("example.com/a b"), "https://duckduckgo.com/?q=example.com%2Fa+b");
        assert_eq!(resolve("http://example.com/x"), "https://example.com/x");
        assert_eq!(resolve("http://192.168.1.20:8080"), "http://192.168.1.20:8080");
        assert_eq!(resolve("192.168.1.20:8080"), "http://192.168.1.20:8080");
        assert_eq!(resolve("hub.local"), "http://hub.local");
        assert_eq!(resolve("localhost:3000"), "http://localhost:3000");
        assert_eq!(resolve(""), "about:blank");
    }
    #[test]
    fn hosts() {
        assert_eq!(host_of("https://User@Ads.Example.com:8443/p?q=1").as_deref(), Some("ads.example.com"));
    }
}
