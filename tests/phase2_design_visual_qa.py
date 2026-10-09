"""Render representative stored design SVGs in an isolated offline Chrome host."""
import base64
from html import escape
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from import_phase2_design import svg_root,save_json


def main():
    local=ROOT/"data/upstream/phase2-design"
    assets=json.loads((ROOT/"data/phase2-design-items.json").read_text(encoding="utf-8"))
    examples=[]
    for source,fragment in (("cmocean","haline"),("Colorcet","glasbey"),("Hero Patterns","skulls"),("Coolshapes","flower-5"),("Wes Anderson","royal1"),("Tabler Icons","acorn")):
        item=next(asset for asset in assets if asset["sourceName"]==source and fragment in asset["id"])
        svg_root(item["code"])
        encoded=base64.b64encode(item["code"].encode()).decode("ascii")
        # SVGs in an img document resolve currentColor independently; use a
        # light isolated host for their default black contours. The product's
        # inline SVG renderer instead inherits the site's white theme color.
        background="#eeeeee" if item["category"]=="pattern" or "currentColor" in item["code"] else "#07090b"
        examples.append((item,f'<article><h2>{escape(item["title"])}</h2><p>{escape(item["sourceName"])}</p><div style="background:{background}"><img src="data:image/svg+xml;base64,{encoded}" alt="{escape(item["title"],quote=True)}"/></div></article>'))
    html='<!doctype html><html><head><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="default-src \'none\'; img-src data:; style-src \'unsafe-inline\'"><title>Motion Lab source SVG verification</title><style>body{background:#07090b;color:#e9eef0;font:16px monospace;margin:24px}main{display:grid;grid-template-columns:repeat(3,1fr);gap:24px}article{border:1px solid #30353a;padding:16px}h1{font-size:24px}h2{font-size:18px}p{color:#00def5}article div{height:280px;display:flex;align-items:center;justify-content:center}img{max-width:100%;max-height:250px;width:250px;height:auto}</style></head><body><h1>Motion Lab original SVG verification</h1><main>'+''.join(html for _,html in examples)+'</main></body></html>'
    page=local/"visual-qa.html";screenshot=local/"visual-qa.png"
    page.write_text(html,encoding="utf-8")
    chrome=Path("C:/Program Files/Google/Chrome/Application/chrome.exe")
    if not chrome.is_file():
        raise SystemExit("Headless Chrome unavailable; source QA page preserved")
    with tempfile.TemporaryDirectory(prefix="chrome-source-qa-",dir=local) as tmp:
        profile=Path(tmp).resolve()
        profile.relative_to(local.resolve())
        argv=[str(chrome),"--headless=new","--disable-background-networking","--disable-component-update","--disable-sync","--no-first-run","--no-default-browser-check","--hide-scrollbars","--window-size=1280,900","--run-all-compositor-stages-before-draw","--virtual-time-budget=2000",f"--user-data-dir={profile}",f"--screenshot={screenshot.resolve()}",page.resolve().as_uri()]
        result=subprocess.run(argv,capture_output=True,timeout=60,creationflags=subprocess.CREATE_NO_WINDOW if sys.platform=="win32" else 0)
        if result.returncode or not screenshot.is_file():
            raise ValueError("Headless SVG source rendering failed: "+result.stderr.decode("utf-8","replace")[-2000:])
    save_json(local/"visual-qa.json",{"renderer":"Installed Chrome headless, isolated temporary profile, no external resource URLs, data:image/svg+xml only","examples":[{"id":item["id"],"category":item["category"],"storedCodeSha256":item["evidence"]["storedCodeSha256"]} for item,_ in examples],"page":page.relative_to(ROOT).as_posix(),"screenshot":screenshot.relative_to(ROOT).as_posix()})
    print(screenshot)


if __name__=="__main__":
    main()
