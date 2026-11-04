const buttons=[...document.querySelectorAll('[data-filter]')];
const posts=[...document.querySelectorAll('.post-card')];
const search=document.querySelector('input[type=search]');
let category=new URLSearchParams(location.search).get('categoria')||'Todos';
if(!buttons.some(b=>b.dataset.filter===category))category='Todos';
const fold=t=>t.normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLocaleLowerCase('pt-BR');
function filter(){let visible=0;for(const p of posts){p.hidden=!(category==='Todos'||p.dataset.category===category)||!fold(p.dataset.search).includes(fold(search?.value||''));if(!p.hidden)visible++;}for(const b of buttons)b.setAttribute('aria-pressed',String(b.dataset.filter===category));const no=document.querySelector('#no-results');if(no)no.hidden=posts.length===0||visible>0;}
buttons.forEach(b=>b.addEventListener('click',()=>{category=b.dataset.filter;filter();}));
search?.addEventListener('input',filter);filter();
