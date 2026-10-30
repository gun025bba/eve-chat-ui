import 'preact';

declare module 'preact' {
  interface PartialInputHTMLAttributes<T extends EventTarget = HTMLInputElement> {
    switch?: boolean;
  }
}
