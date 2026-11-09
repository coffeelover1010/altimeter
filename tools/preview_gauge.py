from pathlib import Path
import sys
sys.path.insert(0,str(Path('cf-ui-research/python-tools').resolve()))
from lupa.lua51 import LuaRuntime
from PIL import Image,ImageDraw,ImageFont
lua=LuaRuntime(unpack_returned_tuples=True)
lua.execute('''
AltimeterForever={}; objects={}; local methods={}
function methods:SetPoint(_,_,_,x,y) self.x=x;self.y=y end
function methods:SetFont(_,s) self.size=s end
function methods:SetText(t) self.text=t end
function methods:SetTextColor(r,g,b) self.r=r;self.g=g;self.b=b end
function methods:SetColorTexture(r,g,b) self.r=r;self.g=g;self.b=b end
function methods:SetSize(w,h) self.w=w;self.h=h end
function methods:SetThickness(w) self.width=w end
function methods:SetStartPoint(_,_,x,y) self.x1=x;self.y1=y end
function methods:SetEndPoint(_,_,x,y) self.x2=x;self.y2=y end
function methods:Hide() self.hidden=true end
function methods:Show() self.hidden=false end
local function object(kind,layer) local o=setmetatable({kind=kind,layer=layer},{__index=methods});table.insert(objects,o);return o end
function methods:CreateLine(_,layer) return object('line',layer) end
function methods:CreateFontString() return object('text','OVERLAY') end
function methods:CreateTexture() return object('texture','OVERLAY') end
setmetatable(methods,{__index=function() return function() end end})
frame=setmetatable({},{__index=methods})
''')
lua.execute(Path('AltimeterForever/addon/Gauge.lua').read_text())
lua.execute('gauge=AltimeterForever.CreateGauge(frame);gauge:SetReading(102,false,true)')
s=3;im=Image.new('RGB',(220*s,268*s),(26,29,32));d=ImageDraw.Draw(im)
d.rounded_rectangle((12*s,12*s,208*s,256*s),radius=9*s,fill=(6,8,9),outline=(97,102,107),width=3*s)
def point(x,y):return (110*s+x*s,134*s-y*s)
objs=list(lua.globals().objects.values());objs.sort(key=lambda o:0 if o.layer=='ARTWORK' else 1)
for o in objs:
 if o.hidden is True:continue
 color=tuple(round((o[k] if isinstance(o[k],(float,int)) else .9)*255) for k in ('r','g','b'))
 if o.kind=='line':d.line([point(o.x1,o.y1),point(o.x2,o.y2)],fill=color,width=max(1,round(o.width*s)))
 elif o.kind=='text':
  font=ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf',round(o.size*s));d.text(point(o.x,o.y),o.text or '',font=font,fill=color,anchor='mm')
 elif o.kind=='texture':
  x,y=point(o.x,o.y);d.rectangle((x-o.w*s/2,y-o.h*s/2,x+o.w*s/2,y+o.h*s/2),fill=color)
Path('AltimeterForever/output').mkdir(exist_ok=True);im.save('AltimeterForever/output/altimeter-preview.png')
