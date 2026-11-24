import sys,re,json,subprocess,hashlib,urllib.parse
from pathlib import Path
from html.parser import HTMLParser
sys.path.insert(0,'/tmp/flle-review-python');import commonmark
D=Path('/financial-low-latency/Documents/newDoc');B=Path('/tmp/flle-flow-review-fix-baseline');parser=commonmark.Parser()
def blocks(s):return [(n.info,n.literal) for n,e in parser.parse(s).walker() if e and n.t=='code_block' and n.info!='mermaid']
class H(HTMLParser):
 def __init__(self):super().__init__();self.stack=[]
 def handle_starttag(self,t,a):
  if t in ('div','span','p','strong','table','tr','td','th'):self.stack.append(t)
 def handle_endtag(self,t):
  if t in ('div','span','p','strong','table','tr','td','th'):assert self.stack and self.stack.pop()==t,(t,self.getpos())
count=0;bash=0;excerpt=[];broken=[]
files=[*sorted(D.glob('[0-9][0-9]-*.md')),D/'README.md',D/'TEACHER-FLOW-NOTES.md']
for p in files:
 s=p.read_text();tree=parser.parse(s)
 h=H();h.feed(commonmark.HtmlRenderer().render(tree));assert not h.stack,(p,h.stack)
 for n,e in tree.walker():
  if not e:continue
  if n.t=='html_block':assert not re.search(r'^\s*```',n.literal,re.M),(p,n.sourcepos)
  if n.t=='code_block' and n.info=='bash':
   r=subprocess.run(['bash','-n'],input=n.literal,text=True,capture_output=True)
   if r.returncode:
    assert '# ... 见脚本全文' in n.literal and p.name.startswith('07'),(p,r.stderr);excerpt.append(p.name)
   else:bash+=1
 links=[n.destination for n,e in tree.walker() if e and n.t in ('link','image')]+re.findall(r'(?:href|src)="([^"]+)"',s)
 for link in links:
  if re.match(r'^[a-z][a-z0-9+.-]*:|^#|^//',link,re.I):continue
  q=p.parent/urllib.parse.unquote(link.split('#')[0]);assert q.exists(),(p,link)
print('PASS','complete Bash',bash,'known incomplete excerpt',len(excerpt),'HTML and file links',len(files))
root=D/'images/course-visuals';n=0
for line in (root/'SHA256SUMS').read_text().splitlines():
 sha,f=line.split(maxsplit=1);assert hashlib.sha256((root/f.lstrip('*')).read_bytes()).hexdigest()==sha; n+=1
print('PASS categories and',n,'central image hashes')
