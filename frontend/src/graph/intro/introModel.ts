export function viewportToPlane(x:number,y:number,width:number,height:number){return {x:(x-width/2)/height*10,y:(height/2-y)/height*10,z:0};}
export function particles(count:number){const p=new Float32Array(count*3);for(let i=0;i<count;i++){p[i*3]=Math.sin(i*123.45)*15;p[i*3+1]=Math.cos(i*71.91)*9;p[i*3+2]=Math.sin(i*39.7)*7-4;}return p;}
