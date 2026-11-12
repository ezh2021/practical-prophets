"use strict";
const media={
1:{chap:"practical-prophets-s01e01-joshua-01-to-05.chapters.json",vtt:"practical-prophets-s01e01-joshua-01-to-05.vtt"},
2:{chap:"practical-prophets-s01e02-joshua-06-to-13.chapters.json",vtt:"practical-prophets-s01e02-joshua-06-to-13.vtt"},
3:{chap:"practical-prophets-s01e03-joshua-14-to-24.chapters.json",vtt:"practical-prophets-s01e03-joshua-14-to-24.vtt"}
};
const allAudio=[...document.querySelectorAll("audio")];let speed=1;
function sec(t){const a=t.trim().replace(",",".").split(":").map(Number);return a.length===3?a[0]*3600+a[1]*60+a[2]:a[0]*60+a[1]}
function parseVtt(raw){const lines=raw.replace(/\r/g,"").split("\n");const cues=[];for(let i=0;i<lines.length;i++){if(!lines[i].includes("-->"))continue;const [a,b]=lines[i].split("-->").map(s=>s.trim().split(/\s+/)[0]);if(!a||!b)continue;const chunks=[];while(++i<lines.length&&lines[i].trim())chunks.push(lines[i]);const body=chunks.join(" ").trim();const voice=body.match(/<v\s+([^>]+)>/i)?.[1]||"";const text=body.replace(/<[^>]+>/g,"").replace(/&amp;/g,"&").replace(/&lt;/g,"<").replace(/&gt;/g,">");if(text)cues.push({start:sec(a),end:sec(b),text,voice})}return cues}
document.querySelectorAll(".episode").forEach(card=>{
 const id=Number(card.dataset.episode),player=card.querySelector("audio"),menu=card.querySelector(".chapters"),panel=card.querySelector(".transcript"),toggle=card.querySelector(".transcript-toggle");
 let cues=[],rows=[],last=-1;
 player.playbackRate=speed;
 player.addEventListener("play",()=>allAudio.forEach(a=>{if(a!==player)a.pause()}));
 card.querySelectorAll("[data-speed]").forEach(b=>b.addEventListener("click",()=>{
  speed=Number(b.dataset.speed);allAudio.forEach(a=>a.playbackRate=speed);
  document.querySelectorAll("[data-speed]").forEach(x=>x.setAttribute("aria-pressed",String(Number(x.dataset.speed)===speed)));
 }));
 card.querySelectorAll("[data-seek]").forEach(b=>b.addEventListener("click",()=>{player.currentTime=Math.max(0,Math.min(player.duration||Infinity,player.currentTime+Number(b.dataset.seek)))}));
 fetch(media[id].chap).then(r=>{if(!r.ok)throw Error("missing");return r.json()}).then(data=>{
  (data.chapters||[]).forEach(ch=>{const option=document.createElement("option");option.value=String(ch.startTime);option.textContent=ch.title;menu.add(option)});
 }).catch(()=>{menu.options[0].textContent="Chapters unavailable"});
 menu.addEventListener("change",()=>{if(menu.value!==""){player.currentTime=Number(menu.value);player.play().catch(()=>{})}});
 toggle.addEventListener("click",async()=>{
  const open=panel.hidden;panel.hidden=!open;toggle.setAttribute("aria-expanded",String(open));toggle.textContent=open?"Hide transcript":"Read along";
  if(!open||rows.length)return;
  panel.textContent="Loading transcript…";
  try{
   const r=await fetch(media[id].vtt);if(!r.ok)throw Error("missing");cues=parseVtt(await r.text());panel.textContent="";
   const label=document.createElement("label");label.className="follow";const checkbox=document.createElement("input");checkbox.type="checkbox";checkbox.className="autofollow";label.append(checkbox,document.createTextNode(" Follow current passage"));panel.append(label);
   rows=cues.map(c=>{const p=document.createElement("p");if(c.voice){const x=document.createElement("span");x.className="speaker";x.textContent=c.voice;p.append(x)}p.append(document.createTextNode(c.text));panel.append(p);return p});
  }catch{panel.textContent="The transcript could not load. Please use the download link above."}
 });
 player.addEventListener("timeupdate",()=>{
  if(!cues.length)return;const i=cues.findIndex(c=>player.currentTime>=c.start&&player.currentTime<c.end);
  if(i===last)return;
  if(last>=0&&rows[last])rows[last].classList.remove("current");last=i;
  if(i>=0&&rows[i]){rows[i].classList.add("current");if(panel.querySelector(".autofollow")?.checked)rows[i].scrollIntoView({block:"nearest"})}
 });
});
