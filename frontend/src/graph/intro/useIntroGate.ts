import { useCallback,useEffect,useState } from 'react';
const KEY='dataopedia_intro_seen_v1';let sessionSeen=false;
export function introSeen(){try{return sessionSeen||Boolean(localStorage.getItem(KEY));}catch{return sessionSeen;}}
export function recordIntro(outcome:string){sessionSeen=true;try{localStorage.setItem(KEY,JSON.stringify({outcome}));}catch{/* In-memory session remains authoritative. */}}
export function useIntroGate(reduced:boolean){const [playing,setPlaying]=useState(()=>{if(reduced){recordIntro('reduced_motion');return false;}return !introSeen();});
 const finish=useCallback((outcome='completed')=>{recordIntro(outcome);setPlaying(false);},[]);
 useEffect(()=>{if(!playing)return;recordIntro('started');const timeout=setTimeout(()=>finish('deadline'),4000);const resize=()=>finish('resize');window.addEventListener('resize',resize);return ()=>{clearTimeout(timeout);window.removeEventListener('resize',resize);};},[playing,finish]);
 useEffect(()=>{if(reduced)finish('reduced_motion');},[reduced,finish]);
 return {playing,finish,replay:()=>{if(!reduced)setPlaying(true);}};
}
