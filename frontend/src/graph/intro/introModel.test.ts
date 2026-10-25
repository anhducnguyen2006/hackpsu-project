import { expect,it } from 'vitest';
import { particles,viewportToPlane } from './introModel';
it('projects viewport centers onto the final camera plane',()=>{expect(viewportToPlane(720,450,1440,900)).toEqual({x:0,y:0,z:0});expect(viewportToPlane(0,0,390,844).y).toBe(5);});
it('uses deterministic bounded decorative buffers',()=>{expect(particles(150)).toHaveLength(450);expect(particles(150)).toEqual(particles(150));});
