import { useThemeColor } from "../../theme/theme";
import { useEffect,useMemo,useRef,useState } from 'react';
import { Canvas,useThree } from '@react-three/fiber';
import { useGSAP } from '@gsap/react';
import gsap from 'gsap';
import * as THREE from 'three';
import type { EvidenceEdge } from '../model';
import { particles,viewportToPlane } from './introModel';
type Entry={id:string;x:number;y:number;color:string;size:number};
gsap.registerPlugin(useGSAP);
function Scene({entries,edges,onReady}:{entries:Entry[];edges:EvidenceEdge[];onReady:()=>void}){const particleColor=useThemeColor("--color-intro-particle"),lineColor=useThemeColor("--color-intro-line");const {camera,size,invalidate}=useThree();const group=useRef<THREE.Group>(null);const points=useMemo(()=>particles(window.innerWidth<768?150:400),[]);const positions=useMemo(()=>new Map(entries.map(e=>[e.id,viewportToPlane(e.x,e.y,size.width,size.height)])),[entries,size]);const lines=useMemo(()=>new Float32Array(edges.slice(0,100).flatMap(e=>{const a=positions.get(e.source),b=positions.get(e.target);return a&&b?[a.x,a.y,0,b.x,b.y,0]:[];})),[edges,positions]);
 useGSAP(()=>{onReady();camera.position.z=16;const t=gsap.timeline({defaults:{ease:'power2.out'},onUpdate:invalidate});t.fromTo(group.current!.scale,{x:.8,y:.8,z:.8},{x:1,y:1,z:1,duration:2.6},0).to(camera.position,{z:10,duration:2.6},0);},{scope:group});
 return <group ref={group}><points><bufferGeometry><bufferAttribute attach="attributes-position" args={[points,3]}/></bufferGeometry><pointsMaterial color={particleColor} size={.018} transparent opacity={.3} depthWrite={false}/></points><lineSegments><bufferGeometry><bufferAttribute attach="attributes-position" args={[lines,3]}/></bufferGeometry><lineBasicMaterial color={lineColor} transparent opacity={.25}/></lineSegments>{entries.map(e=>{const p=positions.get(e.id)!;return <mesh key={e.id} position={[p.x,p.y,0]}><circleGeometry args={[e.size/size.height*10,20]}/><meshBasicMaterial color={e.color}/></mesh>;})}</group>;
}
export default function GraphIntro({entry,edges,onFinish}:{entry:()=>Entry[];edges:EvidenceEdge[];onFinish:(outcome:string)=>void}){const root=useRef<HTMLDivElement>(null);const [entries,setEntries]=useState<Entry[]>([]);const [ready,setReady]=useState(false);
 useEffect(()=>{const frame=requestAnimationFrame(()=>setEntries(entry()));return ()=>cancelAnimationFrame(frame);},[entry]);
 useGSAP(()=>{if(!ready)return;gsap.timeline({defaults:{ease:'power2.out'},onComplete:()=>onFinish('completed')}).fromTo(root.current,{opacity:0},{opacity:1,duration:.5},0).to(root.current,{opacity:0,duration:.6},2.6);},{scope:root,dependencies:[ready],revertOnUpdate:true});
 useEffect(()=>{const timeout=setTimeout(()=>{if(!ready)onFinish('readiness_timeout');},700);return ()=>clearTimeout(timeout);},[ready,onFinish]);
 return <div ref={root} className="graph-intro" onPointerDown={()=>onFinish('interaction')} onKeyDown={()=>onFinish('interaction')}><Canvas frameloop="demand" dpr={[1,1.5]} camera={{position:[0,0,10],fov:53.130102}} fallback={null} gl={{alpha:true,antialias:true}}><Scene entries={entries} edges={edges} onReady={()=>setReady(true)}/></Canvas><div className="graph-intro-caption"><p>From question to evidence</p><button onClick={()=>onFinish('skipped')}>Skip Intro</button></div></div>;
}
