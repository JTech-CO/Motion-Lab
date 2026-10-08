"""Read-only public source probes; no credentials or video downloads."""
import concurrent.futures
import urllib.request

URLS = [
    'https://raw.githubusercontent.com/animate-css/animate.css/3.7.2/LICENSE',
    'https://raw.githubusercontent.com/animate-css/animate.css/3.7.2/animate.css',
    'https://raw.githubusercontent.com/ghosh/uiGradients/master/LICENSE.md',
    'https://raw.githubusercontent.com/ghosh/uiGradients/master/package.json',
    'https://raw.githubusercontent.com/Martz90/vivify/master/LICENSE',
    'https://raw.githubusercontent.com/Martz90/vivify/master/vivify.css',
    'https://raw.githubusercontent.com/Martz90/vivify/master/core/vivify.css',
    'https://raw.githubusercontent.com/erictreacy/mimic.css/master/LICENSE.md',
    'https://raw.githubusercontent.com/kristofferandreasen/wickedCSS/master/LICENSE',
    'https://raw.githubusercontent.com/kristofferandreasen/wickedCSS/master/wickedcss.css',
    'https://raw.githubusercontent.com/elrumordelaluz/csshake/master/LICENSE',
    'https://raw.githubusercontent.com/elrumordelaluz/csshake/master/dist/csshake.css',
    'https://api.github.com/repos/ghosh/uiGradients',
    'https://www.careerhackeralex.com/robots.txt',
    'https://api.github.com/repos/JTech-CO/Motiongraphic/git/trees/main?recursive=1',
]

def probe(url):
    try:
        req=urllib.request.Request(url,headers={'User-Agent':'MotionLab/1.0 (public research; code and palette metadata only)'})
        with urllib.request.urlopen(req,timeout=20) as r:
            body=r.read(5_000_001)
        print(url, len(body), body[:130].decode('utf-8',errors='replace').replace('\n',' '),flush=True)
    except Exception as e:
        print(url,type(e).__name__,str(e),flush=True)

if __name__=='__main__':
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(probe,URLS))
