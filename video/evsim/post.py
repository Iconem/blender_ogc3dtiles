# post.py name [fps] [blur x y w h] [caption]: draw the fake mouse on the frames, encode ui_<name>.mp4
import sys, os, json, time, subprocess, glob
from PIL import Image, ImageDraw, ImageFilter, ImageFont
D=os.path.dirname(os.path.abspath(__file__)); name=sys.argv[1]; fps=sys.argv[2] if len(sys.argv)>2 else "12"
blur=[int(v) for v in sys.argv[3].split(",")] if len(sys.argv)>3 and sys.argv[3] else None
cap=sys.argv[4] if len(sys.argv)>4 else ""
out=os.path.join(D,"cap_"+name)
for _ in range(600):
    if os.path.exists(os.path.join(out,"done.txt")): break
    time.sleep(2)
print(open(os.path.join(out,"done.txt")).read())
meta=json.load(open(os.path.join(out,"meta.json")))
font=ImageFont.truetype("segoeui.ttf",22); small=ImageFont.truetype("segoeui.ttf",17)
ARROW=[(0,0),(0,26),(6,20),(11,31),(15,29),(10,19),(19,19)]
_c=Image.new("RGBA",(21*8,33*8),(0,0,0,0)); _d=ImageDraw.Draw(_c)
_d.polygon([(a*8+6,b*8+6) for a,b in ARROW],fill=(255,255,255,255),outline=(0,0,0,255),width=10)
CURSOR=_c.resize((11,17),Image.LANCZOS)
font=ImageFont.truetype("segoeui.ttf",16)
for i,m in enumerate(meta):
    p=os.path.join(out,"f_%04d.png"%i); im=Image.open(p).convert("RGB")
    if blur:
        x,y,w,h=blur; im.paste(im.crop((x,y,x+w,y+h)).filter(ImageFilter.GaussianBlur(7)),(x,y))
    d=ImageDraw.Draw(im,"RGBA")
    if m["rect"]:
        x0,y0,x1,y1=m["rect"]; d.rectangle([min(x0,x1),min(y0,y1),max(x0,x1),max(y0,y1)],outline=(255,255,255,255),width=2,fill=(255,255,255,28))
    x,y=m["xy"]
    if m["down"]: d.ellipse([x-9,y-9,x+9,y+9],outline=(255,190,40,255),width=2,fill=(255,190,40,70))
    im.paste(CURSOR,(int(x),int(y)),CURSOR); d=ImageDraw.Draw(im,"RGBA")
    if m["key"]:
        tw=d.textlength(m["key"],font=font); bx=16; by=im.height-48
        d.rounded_rectangle([bx,by,bx+tw+20,by+30],6,fill=(20,20,20,215)); d.text((bx+10,by+3),m["key"],font=font,fill=(255,255,255,255))
    if cap:
        tw=d.textlength(cap,font=small); d.rectangle([0,im.height-26,im.width,im.height],fill=(0,0,0,170)) if False else None
        d.rounded_rectangle([im.width//2-tw/2-12,im.height-34,im.width//2+tw/2+12,im.height-6],6,fill=(0,0,0,190)); d.text((im.width//2-tw/2,im.height-32),cap,font=small,fill=(255,255,255,255))
    im.save(p,compress_level=1)
o=os.path.join(D,"ui_"+name+".mp4")
subprocess.check_call(["ffmpeg","-y","-loglevel","error","-framerate",fps,"-i",os.path.join(out,"f_%04d.png"),"-vf","scale=1920:-2","-c:v","libx264","-pix_fmt","yuv420p","-crf","21",o])
for f in glob.glob(os.path.join(out,"f_*.png")): os.remove(f)
print(o, os.path.getsize(o), len(meta),"frames")
