export async function enableControl() {
  if (!window.Capacitor?.Plugins?.TotalControl) return { enabled:false, note:"plugin not available" };
  return await window.Capacitor.Plugins.TotalControl.enableControl();
}
export async function disableControl() {
  if (!window.Capacitor?.Plugins?.TotalControl) return { enabled:false, note:"plugin not available" };
  return await window.Capacitor.Plugins.TotalControl.disableControl();
}
export async function controlStatus() {
  if (!window.Capacitor?.Plugins?.TotalControl) return { enabled:false, note:"plugin not available" };
  return await window.Capacitor.Plugins.TotalControl.status();
}
