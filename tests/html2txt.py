import sys, html.parser
class P(html.parser.HTMLParser):
    def __init__(s): super().__init__(); s.out=[]; s.skip=0
    def handle_starttag(s,t,a):
        if t in('script','style','nav','header','footer'): s.skip+=1
        if t in('p','br','tr','h1','h2','h3','h4','li','pre','div'): s.out.append('\n')
        if t in('td','th'): s.out.append(' | ')
    def handle_endtag(s,t):
        if t in('script','style','nav','header','footer'): s.skip=max(0,s.skip-1)
    def handle_data(s,d):
        if not s.skip: s.out.append(d)
p=P(); p.feed(sys.stdin.read()); import re
print(re.sub(r'\n\s*\n+','\n',''.join(p.out)))
