// Hash routing: #/  #/new  #/c/<id>. Back, refresh, and bookmarks all work,
// and the Worker needs no route config (the server only ever sees "/").

const current = () => location.hash.replace(/^#/, '') || '/';

export const route = $state({ path: current() });

addEventListener('hashchange', () => {
  route.path = current();
});

export function go(path: string) {
  location.hash = path;
}
