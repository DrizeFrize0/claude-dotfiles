//! The start page (new tab): a search box, a tile for the hub and your most visited sites.

use crate::store::Entry;

fn esc(s: &str) -> String {
    s.replace('&', "&amp;").replace('<', "&lt;").replace('>', "&gt;").replace('"', "&quot;")
}

pub fn page(tiles: &[Entry], hub: Option<&str>) -> String {
    let mut items = String::new();
    if let Some(h) = hub {
        items += &format!(r#"<a class="tile hub" href="{}"><b>Jado's hub</b><span>Open</span></a>"#, esc(h));
    }
    for t in tiles.iter().take(8) {
        let title = if t.title.is_empty() { &t.url } else { &t.title };
        let short: String = title.chars().take(26).collect();
        items += &format!(r#"<a class="tile" href="{}"><b>{}</b><span>{}</span></a>"#, esc(&t.url), esc(&short), esc(crate::url::host_of(&t.url).as_deref().unwrap_or("")));
    }
    format!(
        r#"<!doctype html><meta charset="utf-8"><title>New tab</title>
<style>
:root{{color-scheme:light dark}}
body{{margin:0;min-height:100vh;display:grid;place-content:center;gap:28px;font:16px system-ui,sans-serif;background:#14151c;color:#e8e8f0}}
form{{display:flex}} input{{width:min(560px,86vw);padding:14px 20px;border-radius:999px;border:1px solid #ffffff22;background:#ffffff10;color:inherit;font-size:17px;outline:none}}
input:focus{{border-color:#9db4ff}}
.grid{{display:grid;grid-template-columns:repeat(4,150px);gap:14px;justify-content:center}}
.tile{{display:flex;flex-direction:column;gap:4px;padding:16px;border-radius:16px;background:#ffffff0d;text-decoration:none;color:inherit}}
.tile:hover{{background:#ffffff1a}} .tile span{{font-size:12px;opacity:.6}} .hub{{background:#9db4ff22}}
</style>
<form action="https://duckduckgo.com/"><input name="q" placeholder="Search or type an address" autofocus></form>
<div class="grid">{items}</div>"#
    )
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn page_has_tiles_and_escapes() {
        let html = page(&[Entry { url: "https://a.test/?x=1&y=2".into(), title: "<b>Hi</b>".into() }], Some("http://192.168.1.20:8080"));
        assert!(html.contains("Jado's hub") && html.contains("http://192.168.1.20:8080"));
        assert!(html.contains("&lt;b&gt;Hi&lt;/b&gt;") && html.contains("x=1&amp;y=2") && !html.contains("<b>Hi</b>"));
        assert!(!page(&[], None).contains("Jado's hub"));
    }
}
