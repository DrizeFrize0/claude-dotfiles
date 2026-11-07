//! One-time import of Zen (Firefox-style) bookmarks and history.

use crate::store::Store;
use rusqlite::{Connection, OpenFlags};
use std::path::{Path, PathBuf};

/// Where Zen keeps places.sqlite: the Flatpak folder or ~/.zen, newest profile first.
pub fn find_places(home: &Path) -> Option<PathBuf> {
    let roots = [home.join(".var/app/app.zen_browser.zen/.zen"), home.join(".zen"), home.join(".var/app/app.zen_browser.zen/zen")];
    let mut found: Vec<(std::time::SystemTime, PathBuf)> = vec![];
    for root in roots {
        if let Ok(it) = std::fs::read_dir(root) {
            for e in it.flatten() {
                let p = e.path().join("places.sqlite");
                if let Ok(m) = std::fs::metadata(&p) {
                    found.push((m.modified().unwrap_or(std::time::UNIX_EPOCH), p));
                }
            }
        }
    }
    found.sort_by(|a, b| b.0.cmp(&a.0));
    found.into_iter().next().map(|f| f.1)
}

/// Copies from `places` into `store`: (bookmarks, history pages).
pub fn import(places: &Path, store: &Store, now: i64) -> Result<(usize, usize), String> {
    // Zen may be running and holding a lock: read a copy
    let copy = std::env::temp_dir().join(format!("lennox-places-{}.sqlite", std::process::id()));
    std::fs::copy(places, &copy).map_err(|e| e.to_string())?;
    for ext in ["-wal", "-shm"] {
        let side = PathBuf::from(format!("{}{ext}", places.display()));
        if side.exists() {
            let _ = std::fs::copy(&side, PathBuf::from(format!("{}{ext}", copy.display())));
        }
    }
    let result = (|| -> rusqlite::Result<(usize, usize)> {
        let db = Connection::open_with_flags(&copy, OpenFlags::SQLITE_OPEN_READ_ONLY)?;
        let mut marks = 0;
        let mut q = db.prepare(
            "SELECT p.url, COALESCE(b.title, p.title, p.url) FROM moz_bookmarks b JOIN moz_places p ON p.id=b.fk
             WHERE b.type=1 AND p.url LIKE 'http%'",
        )?;
        for row in q.query_map([], |r| Ok((r.get::<_, String>(0)?, r.get::<_, String>(1)?)))? {
            let (url, title) = row?;
            store.add_bookmark(&url, &title, now)?;
            marks += 1;
        }
        let mut pages = 0;
        let mut q = db.prepare("SELECT url, COALESCE(title,''), visit_count FROM moz_places WHERE url LIKE 'http%' AND visit_count>0 ORDER BY last_visit_date DESC LIMIT 5000")?;
        for row in q.query_map([], |r| Ok((r.get::<_, String>(0)?, r.get::<_, String>(1)?, r.get::<_, i64>(2)?)))? {
            let (url, title, visits) = row?;
            for _ in 0..visits.min(50) {
                store.visit(&url, &title, now)?;
            }
            pages += 1;
        }
        Ok((marks, pages))
    })();
    let _ = std::fs::remove_file(&copy);
    for ext in ["-wal", "-shm"] {
        let _ = std::fs::remove_file(format!("{}{ext}", copy.display()));
    }
    result.map_err(|e| e.to_string())
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn imports_from_a_firefox_style_file() {
        let dir = std::env::temp_dir().join(format!("lennox-zen-{}", std::process::id()));
        let profile = dir.join(".zen/abc.Default");
        std::fs::create_dir_all(&profile).unwrap();
        let places = profile.join("places.sqlite");
        let db = Connection::open(&places).unwrap();
        db.execute_batch(
            "CREATE TABLE moz_places (id INTEGER PRIMARY KEY, url TEXT, title TEXT, visit_count INTEGER, last_visit_date INTEGER);
             CREATE TABLE moz_bookmarks (id INTEGER PRIMARY KEY, type INTEGER, fk INTEGER, title TEXT);
             INSERT INTO moz_places VALUES (1,'https://rust-lang.org','Rust',3,100),(2,'https://news.test','',1,200),(3,'place:folder=1','',0,0);
             INSERT INTO moz_bookmarks VALUES (1,1,1,'Rust site'),(2,2,NULL,'folder');",
        )
        .unwrap();
        drop(db);
        assert_eq!(find_places(&dir).unwrap(), places);
        let store = Store::in_memory().unwrap();
        assert_eq!(import(&places, &store, 5).unwrap(), (1, 2));
        assert_eq!(store.bookmarks().unwrap()[0].title, "Rust site");
        assert_eq!(store.most_visited(1).unwrap()[0].url, "https://rust-lang.org");
        let _ = std::fs::remove_dir_all(dir);
    }
}
