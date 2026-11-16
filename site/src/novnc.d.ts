declare module '@novnc/novnc' {
  export default class RFB extends EventTarget {
    constructor(target: HTMLElement, url: string, options?: { credentials?: { password?: string; username?: string; target?: string } });
    scaleViewport: boolean;
    resizeSession: boolean;
    background: string;
    disconnect(): void;
    sendCtrlAltDel(): void;
  }
}
