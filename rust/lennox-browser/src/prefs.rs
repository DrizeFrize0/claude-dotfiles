//! Browser choices: what to wipe when it closes, and per-site permissions.

use std::collections::BTreeMap;
use std::path::Path;

#[derive(Debug, PartialEq, Clone, Copy)]
pub enum Verdict {
    Allow,
    Deny,
    Ask,
}

#[derive(Debug, Default, PartialEq)]
pub struct Prefs {
    pub clear_cookies: bool,
    pub clear_history: bool,
    pub clear_cache: bool,
    /// (site, what) -> verdict; what is camera, microphone, location or notifications
    pub sites: BTreeMap<(String, String), Verdict>,
}

impl Prefs {
    pub fn load(path: &Path) -> Prefs {
        Self::parse(&std::fs::read_to_string(path).unwrap_or_default())
    }

    pub fn parse(text: &str) -> Prefs {
        let mut p = Prefs::default();
        for line in text.lines() {
            let parts: Vec<&str> = line.split_whitespace().collect();
            match parts.as_slice() {
                ["clear_cookies", v] => p.clear_cookies = *v == "yes",
                ["clear_history", v] => p.clear_history = *v == "yes",
                ["clear_cache", v] => p.clear_cache = *v == "yes",
                ["site", host, what, v] => {
                    let verdict = match *v { "allow" => Verdict::Allow, "deny" => Verdict::Deny, _ => Verdict::Ask };
                    p.sites.insert((host.to_string(), what.to_string()), verdict);
                }
                _ => {}
            }
        }
        p
    }

    pub fn to_text(&self) -> String {
        let yn = |b: bool| if b { "yes" } else { "no" };
        let mut t = format!("clear_cookies {}\nclear_history {}\nclear_cache {}\n", yn(self.clear_cookies), yn(self.clear_history), yn(self.clear_cache));
        for ((host, what), v) in &self.sites {
            let v = match v { Verdict::Allow => "allow", Verdict::Deny => "deny", Verdict::Ask => "ask" };
            t += &format!("site {host} {what} {v}\n");
        }
        t
    }

    pub fn save(&self, path: &Path) -> std::io::Result<()> {
        if let Some(d) = path.parent() {
            std::fs::create_dir_all(d)?;
        }
        std::fs::write(path, self.to_text())
    }

    /// What to do when `host` asks for `what`. A saved answer for the site (or a parent domain) wins; otherwise ask.
    pub fn verdict(&self, host: &str, what: &str) -> Verdict {
        let mut rest = host;
        loop {
            if let Some(v) = self.sites.get(&(rest.to_string(), what.to_string())) {
                return *v;
            }
            match rest.split_once('.') {
                Some((_, parent)) if parent.contains('.') => rest = parent,
                _ => return Verdict::Ask,
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn roundtrip_and_verdicts() {
        let mut p = Prefs { clear_cookies: true, ..Default::default() };
        p.sites.insert(("meet.example.com".into(), "camera".into()), Verdict::Allow);
        p.sites.insert(("example.com".into(), "location".into()), Verdict::Deny);
        let again = Prefs::parse(&p.to_text());
        assert_eq!(again, p);
        assert_eq!(again.verdict("meet.example.com", "camera"), Verdict::Allow);
        assert_eq!(again.verdict("a.b.example.com", "location"), Verdict::Deny);
        assert_eq!(again.verdict("example.com", "camera"), Verdict::Ask);
        assert_eq!(Prefs::parse("garbage\n").verdict("x.com", "camera"), Verdict::Ask);
    }
}
