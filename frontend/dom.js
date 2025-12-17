const dom = document.getElementById("dom");
const dctx = dom.getContext("2d");

function drawDOM(bids, asks) {
  dctx.clearRect(0,0,dom.width,dom.height);
  let y=20;
  Object.entries(asks).forEach(([p,q])=>{
    dctx.fillStyle="red";
    dctx.fillText(`${p} ${q}`,10,y); y+=14;
  });
  y+=10;
  Object.entries(bids).forEach(([p,q])=>{
    dctx.fillStyle="green";
    dctx.fillText(`${p} ${q}`,10,y); y+=14;
  });
}
