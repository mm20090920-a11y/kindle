#!/usr/bin/env python3
# 财经看板数据 -> data/dashboard.json (纯标准库)
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

def get_trend(code, n=32):
    try:
        d = json.loads(get('https://web.ifzq.gtimg.cn/appstock/app/minute/query?code='+code, timeout=15, retries=2))
        mins = d['data'][code]['data']['data']
        prices=[]
        for m in mins:
            p=m.split()
            if len(p)>=2:
                try: prices.append(float(p[1]))
                except: pass
        if len(prices)<=n: return prices
        step=len(prices)/float(n)
        return [round(prices[int(i*step)],2) for i in range(n)]
    except Exception as e:
        sys.stderr.write('trend %s fail: %s\n'%(code,e)); return []

out = {'date': time.strftime('%Y-%m-%d'), 'updatedAt': time.strftime('%Y-%m-%d %H:%M')}

# 股指(腾讯)+ 日内走势
try:
    codes=['sh000001','sz399001','sz399006']
    txt = get('https://qt.gtimg.cn/q='+','.join(codes), decode='gbk')
    lines=[l for l in txt.strip().split('\n') if '="' in l]
    stocks=[]
    for idx,line in enumerate(lines):
        f = line.split('="',1)[1].rstrip('";').split('~')
        name=f[1]; cur=float(f[3]); prev=float(f[4]); chg=cur-prev; pct=(chg/prev*100) if prev else 0
        code=codes[idx] if idx<len(codes) else None
        stocks.append({'name':name,'value':f'{cur:.2f}','change':f'{chg:+.2f}','pct':f'{pct:+.2f}%',
                       'up': chg>=0, 'trend': get_trend(code) if code else []})
    out['stocks']=stocks
except Exception as e:
    out['stocks']=[]; sys.stderr.write(f'stocks fail: {e}\n')

# 黄金
try:
    txt = get('https://hq.sinajs.cn/list=hf_XAU', headers={'User-Agent':'kc','Referer':'https://finance.sina.com.cn'}, decode='gbk')
    f = txt.split('="',1)[1].rstrip('";').split(',')
    out['gold']={'name':'黄金·伦敦金','value':f'{float(f[0]):.2f}','unit':'美元/盎司'}
except Exception as e:
    out['gold']=None; sys.stderr.write(f'gold fail: {e}\n')

# 汇率
try:
    d = json.loads(get('https://60s.viki.moe/v2/exchange_rate')).get('data',{})
    rates = {r['currency']:r['rate'] for r in d.get('rates',[])}
    fx=[]
    if rates.get('USD'): fx.append({'name':'美元','value':f"{1/rates['USD']:.3f}"})
    if rates.get('EUR'): fx.append({'name':'欧元','value':f"{1/rates['EUR']:.3f}"})
    if rates.get('HKD'): fx.append({'name':'港币','value':f"{1/rates['HKD']:.3f}"})
    if rates.get('JPY'): fx.append({'name':'100日元','value':f"{100/rates['JPY']:.3f}"})
    out['forex']=fx
except Exception as e:
    out['forex']=[]; sys.stderr.write(f'forex fail: {e}\n')

# 比特币
try:
    b = json.loads(get('https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd,cny&include_24hr_change=true'))['bitcoin']
    out['btc']={'usd':f"{b['usd']:,.0f}",'cny':f"{b['cny']:,.0f}",'pct':f"{b.get('usd_24h_change',0):+.2f}%",'up': b.get('usd_24h_change',0)>=0}
except Exception as e:
    out['btc']=None; sys.stderr.write(f'btc fail: {e}\n')

# 微博/知乎(带链接)
for key,url in [('weibo','https://60s.viki.moe/v2/weibo'),('zhihu','https://60s.viki.moe/v2/zhihu')]:
    try:
        d = json.loads(get(url)).get('data',[])
        out[key]=[{'title':it.get('title',''),'link':it.get('link','')} for it in d[:12] if it.get('title')]
    except Exception as e:
        out[key]=[]; sys.stderr.write(f'{key} fail: {e}\n')

json.dump(out, open('data/dashboard.json','w'), ensure_ascii=False, indent=1)
print('OK:', {k:(len(v) if isinstance(v,list) else ('有' if v else '无')) for k,v in out.items() if k not in ('date','updatedAt')})
print('trend点数:', [len(s.get('trend',[])) for s in out.get('stocks',[])])
