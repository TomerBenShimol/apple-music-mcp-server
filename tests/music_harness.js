const fs = require('node:fs');
const vm = require('node:vm');
const scenario = process.argv[3];
const library = ['A', 'B'].map(id => ({persistentID: () => id, name: () => id,
    artist: () => '', album: () => '', duration: () => 1}));
const playlists = [];
let duplicateCount = 0, deleteCount = 0;
function collection(items, owner) {
    function scoped(item) { return owner ? {...item, owner} : item; }
    const result = () => items.map(scoped);
    Object.defineProperty(result, 'length', {get: () => items.length});
    result.persistentID = () => items.map(item => item.persistentID());
    result.whose = query => () => items.filter(item => item.persistentID() === query.persistentID).map(scoped);
    return new Proxy(result, {get(target, property) {
        return /^\d+$/.test(String(property)) ? scoped(items[Number(property)]) : target[property];
    }});
}
function playlist(id, name, tracks) {
    const state = {name, description: ''};
    const target = {id, items: tracks, persistentID: () => id,
        smart: () => scenario === 'protected', genius: () => false, specialKind: () => 'none'};
    target.tracks = collection(tracks, target);
    return new Proxy(target, {
        get(object, key) { return key in state ? () => state[key] : object[key]; },
        set(object, key, value) { if (key in state) state[key] = value; else object[key] = value; return true; }
    });
}
const original = playlist('P', 'Original', scenario === 'partial-add' ? [] : library.slice());
playlists.push(original);
const music = {
    libraryPlaylists: [{tracks: collection(library)}],
    userPlaylists: collection(playlists),
    make(options) {
        if (options.new !== 'userPlaylist') throw Error('Unsupported playlist class');
        const result = playlist('BKP', options.withProperties.name, []);
        playlists.push(result); return result;
    },
    duplicate(track, {to}) {
        duplicateCount++;
        if ((scenario === 'partial-add' || scenario === 'backup-failure') && duplicateCount === 2)
            throw Error('Simulated Apple Event failure');
        if (scenario === 'rewrite-failure' && duplicateCount === 3) throw Error('Rewrite failed');
        to.items.push(library.find(item => item.persistentID() === track.persistentID()));
    },
    delete(item) {
        if (item.items) { playlists.splice(playlists.indexOf(item), 1); return; }
        deleteCount++;
        if (scenario === 'partial-remove' && deleteCount === 2) throw Error('Delete failed');
        const items = item.owner ? item.owner.items : library;
        items.splice(items.findIndex(track => track.persistentID() === item.persistentID()), 1);
    },
    add() { return undefined; }
};
const context = {Application: () => music, Path: value => value};
vm.createContext(context);
vm.runInContext(fs.readFileSync(process.argv[2], 'utf8'), context);
const operations = {
    create: ['create', {name: 'New'}],
    protected: ['update', {id: 'P', name: 'Changed', dry_run: true}],
    'update-preview': ['update', {id: 'P', name: 'Changed', dry_run: true}],
    import: ['import', {paths: ['/test/a.mp3', '/test/b.mp3']}],
    'partial-add': ['add', {id: 'P', track_ids: ['A', 'B'], skip_duplicates: true}],
    'partial-remove': ['remove_library', {track_ids: ['A', 'B']}],
    'backup-failure': ['reorder', {id: 'P', track_ids: ['B', 'A'], backup_name: 'Recovery'}],
    'rewrite-failure': ['reorder', {id: 'P', track_ids: ['B', 'A'], backup_name: 'Recovery'}],
    reorder: ['reorder', {id: 'P', track_ids: ['B', 'A'], backup_name: 'Recovery'}]
};
const [operation, args] = operations[scenario];
let result, error;
try { result = JSON.parse(context.run([operation, JSON.stringify(args)])); }
catch (exception) { error = String(exception); }
console.log(JSON.stringify({result, error, original: original.tracks.persistentID(),
    name: original.name(), playlists: playlists.map(item => item.name()),
    library: library.map(item => item.persistentID())}));
