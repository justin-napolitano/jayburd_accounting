export function currentPeriodYYYYMM() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,"0")}`;
}
export function monthStart(d = new Date()) {
  return new Date(d.getFullYear(), d.getMonth(), 1);
}
export function monthEnd(d = new Date()) {
  return new Date(d.getFullYear(), d.getMonth()+1, 0);
}
export function fmtMoney(n:number) {
  return (n<0? "-":"") + "$" + Math.abs(n).toFixed(2);
}
