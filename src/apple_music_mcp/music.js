// Fixed JXA program: user input arrives as JSON data, never as executable source.
function run(argv) {
    const op = argv[0], a = JSON.parse(argv[1] || '{}');
    const m = Application('Music');
    function library() { return m.libraryPlaylists[0]; }
    function track(id, container) {
        const found = (container || library()).tracks.whose({persistentID: id})();
        if (found.length !== 1) throw Error('Track not found or ambiguous: ' + id);
        return found[0];
    }
    function playlist(id, writable) {
        const found = m.userPlaylists.whose({persistentID: id})();
        if (found.length !== 1) throw Error('User playlist not found: ' + id);
        const p = found[0];
        if (writable && (p.smart() || p.genius() || String(p.specialKind()) !== 'none'))
            throw Error('Only ordinary user playlists can be edited.');
        return p;
    }
    function song(t) {
        return {id: t.persistentID(), source: 'native', name: t.name(), artist: t.artist(),
                album: t.album(), duration_seconds: t.duration()};
    }
    function info(p) {
        return {id: p.persistentID(), source: 'native', name: p.name(),
                description: p.description(), smart: p.smart(),
                special_kind: String(p.specialKind()), track_count: p.tracks.length};
    }
    function page(items, serialize) {
        const offset = a.offset || 0, limit = a.limit || 50;
        return {items: items.slice(offset, offset + limit).map(serialize),
                total: items.length, offset: offset,
                next_offset: offset + limit < items.length ? offset + limit : null};
    }
    function ids(p) { return p.tracks.persistentID(); }
    function assertIDs(p, expected) {
        const actual = ids(p);
        if (JSON.stringify(actual) !== JSON.stringify(expected))
            throw Error('Music did not retain the requested playlist contents. Read the playlist before retrying.');
    }
    function newPlaylist(props) { return m.make({new: 'userPlaylist', withProperties: props}); }
    // Apple Events are not transactional: report what already happened if a later one fails.
    function each(items, act, label) {
        const done = [];
        try { items.forEach((item, i) => { act(item, i); done.push(item); }); }
        catch (e) { throw Error(String(e) + ' ' + label + ': ' + JSON.stringify(done)); }
    }
    switch (op) {
        case 'status':
            return JSON.stringify({version: m.version(), library_tracks: library().tracks.length,
                                  playlists: m.userPlaylists.length, accessible: true});
        case 'search': {
            const ts = a.query ? m.search(library(), {for: a.query, only: 'all'}) : library().tracks();
            return JSON.stringify(page(ts || [], song));
        }
        case 'track': return JSON.stringify(song(track(a.id)));
        case 'playlists': return JSON.stringify(page(m.userPlaylists(), info));
        case 'playlist': return JSON.stringify(info(playlist(a.id, false)));
        case 'playlist_tracks': return JSON.stringify(page(playlist(a.id, false).tracks(), song));
        case 'create': {
            const p = newPlaylist({name: a.name, description: a.description || ''});
            return JSON.stringify(info(p));
        }
        case 'update': {
            const p = playlist(a.id, true);
            if (a.dry_run) return JSON.stringify({dry_run: true, before: info(p),
                changes: {name: a.name, description: a.description}});
            if (a.name !== undefined) p.name = a.name;
            if (a.description !== undefined) p.description = a.description;
            const result = info(p);
            if ((a.name !== undefined && result.name !== a.name) ||
                (a.description !== undefined && result.description !== a.description))
                throw Error('Music did not retain the playlist changes.');
            return JSON.stringify(result);
        }
        case 'delete_playlist': {
            const p = playlist(a.id, true), before = info(p);
            if (a.dry_run) return JSON.stringify({dry_run: true, playlist: before});
            m.delete(p);
            if (m.userPlaylists.whose({persistentID: a.id})().length)
                throw Error('Music did not delete the playlist.');
            return JSON.stringify({deleted: before});
        }
        case 'add': {
            const p = playlist(a.id, true), before = ids(p);
            const wanted = a.track_ids.filter(id => !a.skip_duplicates || before.indexOf(id) < 0);
            const tracks = wanted.map(id => track(id)); // Resolve all before writing.
            if (a.dry_run) return JSON.stringify({dry_run: true, adding: tracks.map(song)});
            each(wanted, (id, i) => m.duplicate(tracks[i], {to: p}), 'Completed additions');
            assertIDs(p, before.concat(wanted));
            return JSON.stringify({playlist_id: a.id, added: wanted, skipped: a.track_ids.length - wanted.length});
        }
        case 'remove': {
            const p = playlist(a.id, true), before = ids(p);
            a.track_ids.forEach(id => { if (before.indexOf(id) < 0) throw Error('Track absent from playlist: ' + id); });
            const removed = before.filter(id => a.track_ids.indexOf(id) >= 0);
            if (a.dry_run) return JSON.stringify({dry_run: true, removing: removed});
            // Delete playlist-scoped references, in reverse order, preserving library tracks.
            const positions = [];
            for (let i = before.length - 1; i >= 0; --i)
                if (a.track_ids.indexOf(before[i]) >= 0) positions.push(i);
            each(positions, i => m.delete(p.tracks[i]), 'Removed playlist positions');
            assertIDs(p, before.filter(id => a.track_ids.indexOf(id) < 0));
            return JSON.stringify({playlist_id: a.id, removed: removed});
        }
        case 'remove_library': {
            const targets = a.track_ids.map(id => track(id)), before = targets.map(song);
            if (a.dry_run) return JSON.stringify({dry_run: true, removing: before});
            each(a.track_ids, (id, i) => m.delete(targets[i]), 'Completed removals');
            a.track_ids.forEach(id => {
                if (library().tracks.whose({persistentID: id})().length)
                    throw Error('Music did not remove track ' + id + '. Inspect library before retrying.');
            });
            return JSON.stringify({removed: before});
        }
        case 'import': {
            const results = m.add(a.paths.map(path => Path(path)));
            const added = (Array.isArray(results) ? results : [results]).filter(t => t);
            return JSON.stringify({added: added.map(song), unconfirmed: a.paths.length - added.length});
        }
        case 'reorder': {
            const p = playlist(a.id, true), before = ids(p), wanted = a.track_ids;
            if (JSON.stringify(before.slice().sort()) !== JSON.stringify(wanted.slice().sort()))
                throw Error('Reorder requires every current track exactly once per occurrence.');
            const resolved = wanted.map(id => track(id));
            if (a.dry_run) return JSON.stringify({dry_run: true, before: before, after: wanted});
            if (JSON.stringify(before) === JSON.stringify(wanted))
                return JSON.stringify({playlist_id: a.id, changed: false});
            // Keep a recoverable native copy until the complete rewrite verifies.
            const backup = newPlaylist({name: a.backup_name || ('MCP recovery ' + a.id + ' ' + Date.now())});
            try {
                p.tracks().forEach(t => m.duplicate(t, {to: backup}));
                assertIDs(backup, before);
            } catch (e) {
                m.delete(backup);
                throw Error(String(e) + ' The playlist was not changed.');
            }
            try {
                for (let i = before.length - 1; i >= 0; --i) m.delete(p.tracks[i]);
                resolved.forEach(t => m.duplicate(t, {to: p}));
                assertIDs(p, wanted);
            } catch (e) {
                throw Error(String(e) + ' Original contents are saved in playlist ' + backup.name());
            }
            m.delete(backup);
            return JSON.stringify({playlist_id: a.id, changed: true, track_ids: wanted});
        }
        default: throw Error('Unknown Music operation: ' + op);
    }
}
