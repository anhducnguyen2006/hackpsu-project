import { render,screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { expect,it } from 'vitest';
import { DatasetGraph } from '../components/DatasetGraph';
import { EXAMPLE_DATASETS } from '../demo/researchExample';
it('keeps only three floating canvas controls and opens contextual evidence on demand',async()=>{
 render(<DatasetGraph graph={null} datasets={EXAMPLE_DATASETS} question="Study question" cached/>);
 expect(screen.getByRole('button',{name:'Zoom in'})).toBeVisible();
 expect(screen.getByRole('button',{name:'Zoom out'})).toBeVisible();
 expect(screen.getByRole('button',{name:'Fit graph'})).toBeVisible();
 expect(screen.queryByRole('searchbox')).not.toBeInTheDocument();
 expect(screen.queryByRole('region',{name:'All loaded evidence'})).not.toBeInTheDocument();
 await userEvent.keyboard('{Shift>}E{/Shift}');
 // Context menus are available to keyboard users from the graph region.
 const region=screen.getByRole('region',{name:'Scientific knowledge graph'});region.focus();await userEvent.keyboard('e');
 await userEvent.click(screen.getByRole('button',{name:'Browse evidence'}));
 expect(screen.getByRole('region',{name:'All loaded evidence'})).toHaveTextContent('Student Performance');
});
it('opens search context with keyboard and inspects exact variable ownership',async()=>{
 render(<DatasetGraph graph={null} datasets={EXAMPLE_DATASETS} question="Study question" cached/>);
 screen.getByRole('region',{name:'Scientific knowledge graph'}).focus();await userEvent.keyboard('/');
 await userEvent.type(screen.getByRole('searchbox',{name:'Search all evidence'}),'studytime');
 await userEvent.click(screen.getByRole('button',{name:/Inspect studytime/}));
 expect(screen.getByRole('complementary',{name:'Evidence inspector'})).toHaveTextContent('uci:320');
});
it('offers counted checkbox filters without moving inspection into a permanent panel',async()=>{
 render(<DatasetGraph graph={null} datasets={EXAMPLE_DATASETS} question="Study question" cached/>);
 await userEvent.click(screen.getByText('Filters', {selector:'summary'}));
 const variables=screen.getByRole('checkbox',{name:'variable (6)'});
 expect(variables).toBeChecked();
 await userEvent.click(variables);
 expect(variables).not.toBeChecked();
 expect(screen.getByText('4 nodes · 4 relationships · cached evidence')).toBeInTheDocument();
 await userEvent.click(screen.getByRole('button',{name:'Reset filters'}));
 expect(variables).toBeChecked();
 expect(screen.queryByRole('combobox')).not.toBeInTheDocument();
});
it('allows keyboard users to inspect relationship endpoints and returned evidence',async()=>{
 render(<DatasetGraph graph={null} datasets={EXAMPLE_DATASETS} question="Study question" cached/>);
 screen.getByRole('region',{name:'Scientific knowledge graph'}).focus();await userEvent.keyboard('e');
 await userEvent.click(screen.getByRole('button',{name:'Browse evidence'}));
 await userEvent.click(screen.getAllByRole('button',{name:/Study question → Student Performance/})[0]);
 const inspector=screen.getByRole('complementary',{name:'Evidence inspector'});
 expect(inspector).toHaveTextContent('Source');
 expect(inspector).toHaveTextContent('Study question');
 expect(inspector).toHaveTextContent('Target');
 expect(inspector).toHaveTextContent('Student Performance');
 expect(inspector).toHaveTextContent('Verification status');
 expect(inspector).toHaveTextContent('Not supplied');
});
