// Shared rectangular selection for previews. Coordinates are image fractions.
function enableAreaSelection(img, onSelect) {
  const wrapper = document.createElement('div');
  wrapper.style.cssText = 'position:relative;display:block;line-height:0';
  img.parentNode.insertBefore(wrapper, img); wrapper.appendChild(img);
  img.style.cssText += ';cursor:crosshair;user-select:none;touch-action:none';
  img.draggable = false;
  const box = document.createElement('div');
  box.style.cssText = 'position:absolute;border:2px solid #255bce;background:rgba(37,91,206,.14);pointer-events:none;display:none;box-sizing:border-box';
  wrapper.appendChild(box);
  let start = null;
  function point(event) {
    const rect = img.getBoundingClientRect();
    return [Math.max(0, Math.min(1, (event.clientX-rect.left)/rect.width)), Math.max(0, Math.min(1, (event.clientY-rect.top)/rect.height))];
  }
  function bounds(a,b) {return [Math.min(a[0],b[0]), Math.min(a[1],b[1]), Math.max(a[0],b[0]), Math.max(a[1],b[1])];}
  function paint(rect) {
    box.style.left = (img.offsetLeft + rect[0]*img.clientWidth)+'px';
    box.style.top = (img.offsetTop + rect[1]*img.clientHeight)+'px';
    box.style.width = ((rect[2]-rect[0])*img.clientWidth)+'px';
    box.style.height = ((rect[3]-rect[1])*img.clientHeight)+'px';
    box.style.display = 'block';
  }
  img.addEventListener('pointerdown', event => {
    if(event.button !== 0 || img.dataset.selectDisabled === 'true') return;
    event.preventDefault(); start=point(event); img.setPointerCapture(event.pointerId); paint(bounds(start,start));
  });
  img.addEventListener('pointermove', event => {if(start)paint(bounds(start,point(event)));});
  img.addEventListener('pointerup', event => {
    if(!start)return; const rect=bounds(start,point(event)); start=null;
    if(img.hasPointerCapture(event.pointerId))img.releasePointerCapture(event.pointerId);
    if((rect[2]-rect[0])*img.clientWidth<4 || (rect[3]-rect[1])*img.clientHeight<4){box.style.display='none';return;}
    onSelect(rect);
  });
  img.addEventListener('pointercancel',()=>{start=null;box.style.display='none'});
  img.addEventListener('load',()=>{box.style.display='none'});
}
