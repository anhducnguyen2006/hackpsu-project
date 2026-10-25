import { Component,type ReactNode } from 'react';
export class GraphBoundary extends Component<{children:ReactNode;fallback:ReactNode;onFailure?:()=>void},{failed:boolean}>{state={failed:false};static getDerivedStateFromError(){return {failed:true};}componentDidCatch(){this.props.onFailure?.();}render(){return this.state.failed?this.props.fallback:this.props.children;}}
