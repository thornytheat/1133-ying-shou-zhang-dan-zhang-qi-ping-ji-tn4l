function svgNode(tag, attributes, label) {
    const element = document.createElementNS('http://www.w3.org/2000/svg', tag);
    Object.entries(attributes).forEach(([key, value]) => element.setAttribute(key, value));
    if (label !== undefined) element.textContent = text(label);
    return element;
}

function figure(target, width, height) {
    const svg = svgNode('svg', {viewBox:`0 0 ${width} ${height}`, role:'img', 'aria-label':target.dataset.axis});
    target.append(svg);
    return svg;
}

function drawProjectChart(target, points) {
    const ordered = [...points].sort((a,b)=>a.value-b.value);
    const svg=figure(target,650,240);
    if (!ordered.length) return;
    const max=Math.max(...ordered.map(p=>p.value),1e-6);
    const width=560/ordered.length;
    let trace=`M 40 ${198-ordered[0].value/max*146}`;
    ordered.forEach((point, i)=> {
        const x=40+i*width;
        const y=198-point.value/max*146;
        trace += ` V ${y} H ${x+width}`;
        if (i%2===0) svg.append(svgNode('text',{x,y:218,class:'chart-caption'},point.label.slice(0,6)));
    });
    svg.append(svgNode('line',{x1:40,x2:600,y1:198,y2:198,class:'chart-grid'}));
    svg.append(svgNode('path',{d:trace,class:'series-line'}));
}
