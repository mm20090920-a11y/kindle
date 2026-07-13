#!/usr/bin/env python3
import urllib.request, json, time, sys

def get(url, headers=None, decode='utf-8', timeout=20, retries=3):
    last=None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers=headers or {'User-Agent':'kindle-clock/1.0'})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read().decode(decode, 'ignore')
        except Exception as e:
            last=e; time.sleep(2)
    raise last

def downsample(prices, n=32):
    if len(prices)<=n: return prices
    step=len(prices)/float(n); return [round(prices[int(i*step)],2) for i in range(n)]

def get_trend(code):
    try:
        d = json.loads(get('https://web.ifzq.gtimg.cn/appstock/app/minute/query?code='+code, timeout=15, retries=2))
        mins = d['data'][code]['data']['data']; prices=[]
        for m in mins:
            p=m.split()
            if len(p)>=2:
                try: prices.append(float(p[1]))
                except: pass
        return downsample(prices)
    except Exception as e:
        sys.stderr.write('trend %s: %s\n'%(code,e)); return []

# 读上一次数据(用于汇率的"日涨跌")
try: prev = json.load(open('data/dashboard.json'))
except Exception: prev = {}
prev_fx = {f['name']: f.get('value') for f in prev.get('forex',[])} if isinstance(prev.get('forex'),list) else {}

out = {'date': time.strftime('%Y-%m-%d'), 'updatedAt': time.strftime('%Y-%m-%d %H:%M')}

# 股指 + 走势
try:
    codes=['sh000001','sz399001','sz399006','hkHSI']
    txt = get('https://qt.gtimg.cn/q='+','.join(codes), decode='gbk')
    lines=[l for l in txt.strip().split('\n') if '="' in l]; stocks=[]
    for idx,line in enumerate(lines):
        f = line.split('="',1)[1].rstrip('";').split('~')
        name=f[1]; cur=float(f[3]); pc=float(f[4]); chg=cur-pc; pct=(chg/pc*100) if pc else 0
        code=codes[idx] if idx<len(codes) else None
        stocks.append({'name':name,'value':f'{cur:.2f}','change':f'{chg:+.2f}','pct':f'{pct:+.2f}%','up':chg>=0,'trend':get_trend(code) if code else []})
    out['stocks']=stocks
except Exception as e:
    out['stocks']=[]; sys.stderr.write(f'stocks: {e}\n')

# 黄金 + 涨跌(昨收=field[7])
try:
    f = get('https://hq.sinajs.cn/list=hf_XAU', headers={'User-Agent':'kc','Referer':'https://finance.sina.com.cn'}, decode='gbk').split('="',1)[1].rstrip('";').split(',')
    cur=float(f[0]); pc=float(f[7]); chg=cur-pc; pct=(chg/pc*100) if pc else 0
    out['gold']={'name':'黄金·伦敦金','value':f'{cur:.2f}','unit':'美元/盎司','change':f'{chg:+.2f}','pct':f'{pct:+.2f}%','up':chg>=0}
except Exception as e:
    out['gold']=None; sys.stderr.write(f'gold: {e}\n')

# 汇率 + 日涨跌(与上次对比)
try:
    d = json.loads(get('https://60s.viki.moe/v2/exchange_rate')).get('data',{})
    rates = {r['currency']:r['rate'] for r in d.get('rates',[])}
    fx=[]
    for name,code,mult in [('美元','USD',1),('欧元','EUR',1),('港币','HKD',1),('100日元','JPY',100)]:
        if not rates.get(code): continue
        v=mult/rates[code]; entry={'name':name,'value':f'{v:.3f}'}
        pv=prev_fx.get(name)
        if pv:
            try:
                chg=v-float(pv); pct=(chg/float(pv)*100) if float(pv) else 0
                entry.update({'change':f'{chg:+.4f}','pct':f'{pct:+.2f}%','up':chg>=0})
            except: pass
        fx.append(entry)
    out['forex']=fx
except Exception as e:
    out['forex']=[]; sys.stderr.write(f'forex: {e}\n')

# 比特币 + 走势(coingecko)
try:
    b = json.loads(get('https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd,cny&include_24hr_change=true'))['bitcoin']
    trend=[]
    try:
        mc=json.loads(get('https://api.coingecko.com/api/v3/coins/bitcoin/market_chart?vs_currency=usd&days=1'))
        trend=downsample([p[1] for p in mc.get('prices',[])])
    except Exception as e2: sys.stderr.write(f'btc trend: {e2}\n')
    out['btc']={'usd':f"{b['usd']:,.0f}",'cny':f"{b['cny']:,.0f}",'pct':f"{b.get('usd_24h_change',0):+.2f}%",'up':b.get('usd_24h_change',0)>=0,'trend':trend}
except Exception as e:
    out['btc']=None; sys.stderr.write(f'btc: {e}\n')

for key,url in [('weibo','https://60s.viki.moe/v2/weibo'),('zhihu','https://60s.viki.moe/v2/zhihu')]:
    try:
        d = json.loads(get(url)).get('data',[])
        out[key]=[{'title':it.get('title',''),'link':it.get('link','')} for it in d[:12] if it.get('title')]
    except Exception as e:
        out[key]=[]; sys.stderr.write(f'{key}: {e}\n')

# 百度热搜(官方接口)
try:
    d = json.loads(get('https://top.baidu.com/api/board?platform=wise&tab=realtime', headers={'User-Agent':'Mozilla/5.0'}))
    cont = d['data']['cards'][0]['content']
    lst = cont[0]['content'] if (cont and isinstance(cont[0],dict) and isinstance(cont[0].get('content'),list)) else cont
    out['baidu']=[{'title':(it.get('word') or it.get('query') or ''),'link':it.get('url','')} for it in lst[:15] if (it.get('word') or it.get('query'))]
except Exception as e:
    out['baidu']=[]; sys.stderr.write(f'baidu: {e}\n')

# AI 热榜:复用已抓好的 AI日报 data/daily.json
try:
    dd = json.load(open('data/daily.json'))
    ai=[]
    for sec in dd.get('sections',[]):
        for it in sec.get('items',[]):
            if it.get('title'): ai.append({'title':it['title'],'link':it.get('sourceUrl') or it.get('url') or ''})
    out['ai']=ai[:12]
except Exception as e:
    out['ai']=[]; sys.stderr.write(f'ai: {e}\n')

json.dump(out, open('data/dashboard.json','w'), ensure_ascii=False, indent=1)
print('OK stocks_trend:',[len(s.get('trend',[])) for s in out.get('stocks',[])],'| gold_chg:',out.get('gold',{}).get('pct') if out.get('gold') else None,'| fx:',[(f['name'],f.get('pct')) for f in out.get('forex',[])])
