 //layer switching functionality
 document.addEventListener('click', function(event) {
    if (event.target && event.target.classList.contains('layerSwitcher')) {
      const layerId = event.target.id;
      console.log('Layer ID:', layerId);
      checkedStatus = document.getElementById(layerId).checked;
      if(layerId == "search_layer"){
          if(checkedStatus){
            map.addLayer(liveLayer);
          }
          else{
            map.removeLayer(liveLayer);
          }
      }
      else if(layerId=="search_bbox_layer"){
        if(checkedStatus){
            map.addLayer(geojsonLayer);
          }
          else{
            map.removeLayer(geojsonLayer);
          }
      }
      else if(layerId == "compute_layer"){
        // console.log("entered compute_layer");
        // console.log("compute checked status: "+checkedStatus);
        // console.log(computeLayer);
        
        if(checkedStatus){
          // console.log("addRasterLayer");
          map.addLayer(computeLayer); //remove comment
        }
        else{
          // console.log("removeRasterLayer");
          map.removeLayer(computeLayer);
          
        }
      }

      
    }

    // //zoom to layer click on layerswitcher
    // if (event.target && event.target.classList.contains('zoom-to-layer')) {
    //   const zoomId = event.target.id;
    //   console.log('zoom ID:', zoomId);

    //   if(zoomId == "search_zoom"){
    //     //get bound at the time of apply and fit it. I will do it later.
    //   }
    // }
  });


 

// Function to zoom to a layer
function zoomToLayer(layerName) {
const layers = {
"liveLayer": liveLayer,
"geojsonLayer": geojsonLayer,
"computeLayer": computeLayer
};
const layer = layers[layerName];
if (layer) {
  if (layer.getBounds) {
      // For vector layers
      map.fitBounds(layer.getBounds());
  } else if (layer.getBounds === undefined && layer._bounds) {
      // For raster layers
      map.fitBounds(layer._bounds);
  } else {
      console.error(`Layer ${layerName} does not support bounding box`);
  }
  // console.log(`Zooming to ${layerName}`);
} else {
  console.error(`Layer ${layerName} not found`);
}
}

// Query all zoom icons with an ID starting with "zoom_"
document.querySelectorAll('i[id^="zoom_"]').forEach(icon => {
icon.addEventListener('click', function() {
  const layerName = this.id.split('_')[1];
  zoomToLayer(layerName);
});
});

  