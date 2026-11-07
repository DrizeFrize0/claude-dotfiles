//! Bookmarks and history, in one small SQLite file.

use rusqlite::{params, Connection};
use std::path::Path;

pub struct Store {
    db: Connection,
}

#[derive(Debug, PartialEq, Clone)]
pub struct Entry {
    pub url: String,
    pub title: String,
}

impl Store {
    pub fn open(path: &Path) -> rusqlite::Result<Store> {
        if let Some(dir) = path.parent() {
            let _ = std::fs::create_dir_all(dir);
        }
        Self::from(Connection::open(path)?)
    }

    pub fn in_memory() -> rusqlite::Result<Store> {
        Self::from(Connection::open_in_memory()?)
    }

    fn from(db: Connection) -> rusqlite::Result<Store> {
        db.execute_batch(
            "PRAGMA journal_mode=WAL;
             CREATE TABLE IF NOT EXISTS bookmarks (url TEXT PRIMARY KEY, title TEXT NOT NULL, added INTEGER NOT NULL);
             CREATE TABLE IF NOT EXISTS history (url TEXT PRIMARY KEY, title TEXT NOT NULL, visits INTEGER NOT NULL, last INTEGER NOT NULL);
             CREATE INDEX IF NOT EXISTS history_last ON history(last DESC);",
        )?;
        Ok(Store { db })
    }

    pub fn add_bookmark(&self, url: &str, title: &str, now: i64) -> rusqlite::Result<()> {
        self.db.execute(
            "INSERT INTO bookmarks(url,title,added) VALUES(?1,?2,?3) ON CONFLICT(url) DO UPDATE SET title=excluded.title",
            params![url, title, now],
        )?;
        Ok(())
    }

    pub fn remove_bookmark(&self, url: &str) -> rusqlite::Result<bool> {
        Ok(self.db.execute("DELETE FROM bookmarks WHERE url=?1", params![url])? > 0)
    }

    pub fn is_bookmarked(&self, url: &str) -> bool {
        self.db.query_row("SELECT 1 FROM bookmarks WHERE url=?1", params![url], |_| Ok(())).is_ok()
    }

    pub fn bookmarks(&self) -> rusqlite::Result<Vec<Entry>> {
        let mut q = self.db.prepare("SELECT url,title FROM bookmarks ORDER BY added DESC, title")?;
        let rows = q.query_map([], |r| Ok(Entry { url: r.get(0)?, title: r.get(1)? }))?;
        rows.collect()
    }

    pub fn visit(&self, url: &str, title: &str, now: i64) -> rusqlite::Result<()> {
        if url.starts_with("about:") || url.starts_with("lennox:") {
            return Ok(());
        }
        self.db.execute(
            "INSERT INTO history(url,title,visits,last) VALUES(?1,?2,1,?3)
             ON CONFLICT(url) DO UPDATE SET visits=visits+1, last=excluded.last, title=CASE WHEN excluded.title<>'' THEN excluded.title ELSE title END",
            params![url, title, now],
        )?;
        Ok(())
    }

    pub fn recent(&self, limit: usize) -> rusqlite::Result<Vec<Entry>> {
        let mut q = self.db.prepare("SELECT url,title FROM history ORDER BY last DESC LIMIT ?1")?;
        let rows = q.query_map(params![limit as i64], |r| Ok(Entry { url: r.get(0)?, title: r.get(1)? }))?;
        rows.collect()
    }

    pub fn most_visited(&self, limit: usize) -> rusqlite::Result<Vec<Entry>> {
        let mut q = self.db.prepare("SELECT url,title FROM history ORDER BY visits DESC, last DESC LIMIT ?1")?;
        let rows = q.query_map(params![limit as i64], |r| Ok(Entry { url: r.get(0)?, title: r.get(1)? }))?;
        rows.collect()
    }

    /// For the address bar: bookmarks and history that contain every word.
    pub fn search(&self, text: &str, limit: usize) -> rusqlite::Result<Vec<Entry>> {
        let words: Vec<String> = text.split_whitespace().map(|w| format!("%{}%", w.replace('%', "").replace('_', ""))).collect();
        if words.is_empty() {
            return Ok(vec![]);
        }
        let cond = (0..words.len()).map(|i| format!("(url LIKE ?{0} OR title LIKE ?{0})", i + 1)).collect::<Vec<_>>().join(" AND ");
        let sql = format!(
            "SELECT url,title FROM (SELECT url,title,2 AS rank,added AS t FROM bookmarks WHERE {cond}
              UNION ALL SELECT url,title,1,last FROM history WHERE {cond}) GROUP BY url ORDER BY MAX(rank) DESC, MAX(t) DESC LIMIT {limit}"
        );
        let mut q = self.db.prepare(&sql)?;
        let rows = q.query_map(rusqlite::params_from_iter(words.iter()), |r| Ok(Entry { url: r.get(0)?, title: r.get(1)? }))?;
        rows.collect()
    }

    pub fn clear_history(&self) -> rusqlite::Result<usize> {
        self.db.execute("DELETE FROM history", [])
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn bookmarks_history_search() {
        let s = Store::in_memory().unwrap();
        s.add_bookmark("https://rust-lang.org", "Rust", 1).unwrap();
        s.add_bookmark("https://rust-lang.org", "Rust Language", 2).unwrap();
        assert_eq!(s.bookmarks().unwrap(), vec![Entry { url: "https://rust-lang.org".into(), title: "Rust Language".into() }]);
        assert!(s.is_bookmarked("https://rust-lang.org"));
        s.visit("https://news.test/a", "News", 10).unwrap();
        s.visit("https://news.test/a", "", 11).unwrap();
        s.visit("about:blank", "", 12).unwrap();
        s.visit("https://other.test", "Other", 13).unwrap();
        assert_eq!(s.recent(5).unwrap().len(), 2);
        assert_eq!(s.most_visited(1).unwrap()[0].title, "News");
        assert_eq!(s.search("rust lang", 5).unwrap().len(), 1);
        assert_eq!(s.search("news", 5).unwrap()[0].url, "https://news.test/a");
        assert!(s.search("zzz", 5).unwrap().is_empty());
        assert!(s.remove_bookmark("https://rust-lang.org").unwrap());
        assert!(!s.is_bookmarked("https://rust-lang.org"));
        assert_eq!(s.clear_history().unwrap(), 2);
    }
}
