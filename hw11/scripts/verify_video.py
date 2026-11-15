"""Inspect the actual OBS MP4; emit contact sheet for separate visual review.

Optional local dependencies: av==16.0.1, pillow (analysis lock).
"""
from pathlib import Path
import hashlib,json,sys
import av
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[1]
path=Path(sys.argv[1] if len(sys.argv)>1 else json.loads((ROOT/'results/record-output.json').read_text())['outputPath'])
container=av.open(str(path));video=container.streams.video[0]
duration=container.duration/av.time_base
result={'path':str(path.resolve()),'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'duration_seconds':duration,'width':video.width,'height':video.height,'fps':str(video.average_rate),'streams':[{'type':s.type,'codec':s.codec_context.name} for s in container.streams],'subtitle_streams':len(container.streams.subtitles)}
times=[2,45,85,110,135,175,215,240,265,282,300,325,350,375,400,425]
shots=[]
for second in times:
 if second>=duration:continue
 container.seek(int(second/video.time_base),stream=video)
 frame=next(container.decode(video=0));picture=frame.to_image()
 picture.save(f'/tmp/hw11-video-frame-{second}.png')
 picture.thumbnail((640,360));shots.append((second,picture))
container.close();container=av.open(str(path));maximum=0.;count=0
if container.streams.audio:
 for frame in container.decode(audio=0):
  maximum=max(maximum,float(abs(frame.to_ndarray()).max()));count+=1
container.close()
result.update(audio_max_abs=maximum,audio_frames=count,sample_times_seconds=[s for s,_ in shots],visual_review='pending')
assert result['width']==1920 and result['height']==1080
assert result['subtitle_streams']==0 and maximum==0
sheet=Image.new('RGB',(1920,390*((len(shots)+2)//3)),(35,35,35));draw=ImageDraw.Draw(sheet)
for i,(second,picture) in enumerate(shots):
 x=i%3*640;y=i//3*390;sheet.paste(picture,(x,y));draw.text((x+10,y+363),f'{second} s',fill='white')
sheet.save('/tmp/hw11-video-contact.jpg')
(ROOT/'results/video-review.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
