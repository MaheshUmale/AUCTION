const fp = document.getElementById("fp");
const ctx = fp.getContext("2d");
let bars = [];

function drawFP() {
  ctx.clearRect(0,0,fp.width,fp.height);
  bars.forEach((b,i)=>{
    Object.entries(b.levels).forEach(([p,v])=>{
      let y = fp.height - p*5%fp.height;
      let x = i*80;
      let heat = Math.min(Math.abs(v.abs)/50,1);
      ctx.fillStyle = v.ask>v.bid
        ? `rgba(0,200,0,${heat})`
        : `rgba(200,0,0,${heat})`;
      ctx.fillRect(x,y,70,14);
      ctx.fillStyle="#000";
      ctx.fillText(`${v.bid}|${v.ask}`,x+2,y+11);
    });
  });
}
