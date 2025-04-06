//draw start 
var drawToolbar;   
var rectangle;
document.addEventListener('DOMContentLoaded', function() {
  drawToolbar = document.querySelector('.leaflet-draw-toolbar');
  if (drawToolbar) {
    drawToolbar.style.display = 'none';
  }
});

// Initialize the FeatureGroup to store editable layers
var drawnItems = new L.FeatureGroup();
map.addLayer(drawnItems);

// Initialize the draw control and pass it the FeatureGroup of editable layers
var drawControl = new L.Control.Draw({
    edit: {
        featureGroup: drawnItems
    },
    draw: false // Disable built-in draw options
});
map.addControl(drawControl);

// Draw handlers
var drawHandlers = {
    point: new L.Draw.Marker(map),
    polygon: new L.Draw.Polygon(map, { 
      shapeOptions: { 
        // color: 'red',
        fillOpacity: 0.1,  
        // weight: 1 // Border weight 
      } 
    }),
    rectangle: new L.Draw.Rectangle(map, { 
      shapeOptions: { 
        fillOpacity: 0.1,  
      } 
    })
};

// Draw buttons event listeners
document.getElementById('draw-point').addEventListener('click', function () {
    // Clear existing layers before drawing a new one
    drawnItems.clearLayers();
    if(rectangle){
      map.removeLayer(rectangle);
    }
    drawHandlers.point.enable();
    drawHandlers.polygon.disable();
    drawHandlers.rectangle.disable();
});
document.getElementById('draw-polygon').addEventListener('click', function () {
    // Clear existing layers before drawing a new one
    drawnItems.clearLayers();
    if(rectangle){
      map.removeLayer(rectangle);
    }
    drawHandlers.point.disable();
    drawHandlers.polygon.enable();
    drawHandlers.rectangle.disable();
});
document.getElementById('draw-rectangle').addEventListener('click', function () {
    // Clear existing layers before drawing a new one
    drawnItems.clearLayers();
    if(rectangle){
      map.removeLayer(rectangle);
    }
    drawHandlers.point.disable();
    drawHandlers.polygon.disable();
    drawHandlers.rectangle.enable();
});

// Convert radius in kilometers to degrees 
function metersToDegrees(kilometers) { 
    const earthRadius = 6371000; // in meters 
    const degToRad = Math.PI / 180; 
    const radToDeg = 180 / Math.PI; 
    const deltaDeg = kilometers / (earthRadius * degToRad); 
    return deltaDeg * radToDeg; 
}

function updateDrawnItemBbox(layer){
    if (!(layer instanceof L.Marker)) { //for polygons and rectangles
        // console.log("entered if");
        var bd = layer.getBounds();
        export_params_bbox_changed = true;
        export_params.bbox = `${bd.getWest()},${bd.getSouth()},${bd.getEast()},${bd.getNorth()}`;
        // console.log(export_params.bbox);
        document.getElementById("map-window-content").innerHTML = export_params.bbox;
        // console.log(document.getElementById("map-window-content").innerHTML);

        if (drawToolbar) {
          drawToolbar.style.display = 'none';
        }

    } else { //for markers
        // console.log("entered else");
        var radiusInKiloMeters = 70; // radius in kilometers
        var radiusInDegrees = metersToDegrees(radiusInKiloMeters);

        var latlng = layer.getLatLng();
        var lat = latlng.lat;
        var lng = latlng.lng;

        export_params_bbox_changed = true;
        export_params.bbox = `${lng - radiusInDegrees},${lat - radiusInDegrees},${lng + radiusInDegrees},${lat + radiusInDegrees}`;
        // console.log("export-params-bbox: "+ export_params_bbox);
        document.getElementById("map-window-content").innerHTML = export_params.bbox;
        if (drawToolbar) {
          drawToolbar.style.display = 'none';
        }

        var bounds = [
          [lat - radiusInDegrees, lng - radiusInDegrees], // Southwest corner
          [lat + radiusInDegrees, lng + radiusInDegrees]  // Northeast corner
        ];      
        rectangle = L.rectangle(bounds, {fillOpacity: 0.1, opacity: 0.6}).addTo(map);
    }
  }

let activeDrawHandler = null;
// Event listener for the drawstart event 
map.on(L.Draw.Event.DRAWSTART, function (e) {  
  if (drawToolbar) {
    drawToolbar.style.display = 'block';
  }
});

// Event for creating new layers
map.on(L.Draw.Event.CREATED, function (event) {
    // Clear existing layers before adding the new layer
    drawnItems.clearLayers();
    if(rectangle){
      map.removeLayer(rectangle);
    }
    var layer = event.layer;
    drawnItems.addLayer(layer);
    // console.log("entered here - created");
    updateDrawnItemBbox(layer);

    var geojson = layer.toGeoJSON();

    // Calculate the area using turf.js
    var area = turf.area(geojson);

    // Convert area to square kilometers (optional)
    var areaKm2 = area / 1000000;
    // console.log('Area: ' + areaKm2.toFixed(2) + ' square kilometers');

    if(areaKm2 > 500){
      // showMessage('success', "message");
      showMessage('warning', 10000, "Please Select Smaller Area of Interest. Eg. smaller than 500 SQ.Km.");
    }
});

      