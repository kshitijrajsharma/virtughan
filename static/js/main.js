//adjust container height start
document.addEventListener('DOMContentLoaded', function () {
    function adjustMainHeight() {
        const header = document.querySelector('header');
        const tabs = document.getElementById('filterTab');
        const info = document.getElementById('info');
        const tabPanels = document.querySelectorAll('.tab-scrollable-content');

        // Get whichever has the maximum height between the buttons at the bottom live and export tabs
        var buttons = document.querySelectorAll('.bottom-sticky-buttons');

        var maxHeight = 0;

        // Loop through the buttons to find the one with the highest height
        buttons.forEach(function(button) {
            var buttonHeight = button.offsetHeight;
            if (buttonHeight > maxHeight) {
                maxHeight = buttonHeight;
            }
        });

        var containerHeight = header.offsetHeight + tabs.offsetHeight + maxHeight + 70; // extra 70 added for bottom sticky contents

        // Check if the viewport is a tablet or mobile
        var isTabletOrMobile = window.innerWidth <= 1024;

        // Calculate the height based on the condition
        var percentageHeight = isTabletOrMobile ? 90 : 100; // Use 90% for tablets and mobile, 100% otherwise
        var heightCalculation = `calc(${percentageHeight}vh - ${containerHeight}px)`;

        tabPanels.forEach(function(tabPanel) {
            tabPanel.style.height = heightCalculation;
        });
    }

    // Initial check on page load
    adjustMainHeight();

    // Update on window resize
    window.addEventListener('resize', adjustMainHeight);
});
//adjust container height end


//leftbar tab start
document.addEventListener('DOMContentLoaded', function() {
    const tabs = document.querySelectorAll('.tab');
    const tabPanels = document.querySelectorAll('.tab-panel');

    tabs.forEach((tab, index) => {
      tab.addEventListener('click', () => {
        tabs.forEach(tab => tab.classList.remove('border-blue-500', 'text-blue-500'));
        tab.classList.add('border-blue-500', 'text-blue-500');
        tabPanels.forEach(panel => panel.classList.add('hidden'));
        tabPanels[index].classList.remove('hidden');
      });
    });

    // Activate the first tab by default
    tabs[0].classList.add('border-blue-500', 'text-blue-500');
    tabPanels[0].classList.remove('hidden');

  });

  //leftbar tab end

//band box change - advance filter (formula) start
document.getElementById("band1").addEventListener("change", updateBandsBox);
document.getElementById("band2").addEventListener("change", updateBandsBox);

function updateBandsBox() {
    const band1_v = document.getElementById("band1").value;
    const band2_v = document.getElementById("band2").value;

    tile_params.band1 = band1_v.toLowerCase();
    tile_params.band2 = band2_v.toLowerCase();

    export_params.band1 = band1_v.toLowerCase(); //setting the same params for now.
    export_params.band2 = band2_v.toLowerCase();

    const mappedBands = new Set();

    if (band1_v) {
        mappedBands.add(`Band1 (${band1_v})`);
    }

    if (band2_v) {
        mappedBands.add(`Band2 (${band2_v})`);
    }

    const bandsArray = Array.from(mappedBands);

    const mappedBandsList = document.getElementById("mapped-bands");
    mappedBandsList.innerHTML = bandsArray.map(band => `<li class="attribute-item hover:bg-gray-100 p-1">${band}</li>`).join('');

    // if (bandsArray.length > 0) {
    //     document.getElementById("bandsSection").classList.remove("hidden");
    // } else {
    //     document.getElementById("bandsSection").classList.add("hidden");
    // }
}
//band box change - advance filter (formula) end



//buttons and filters start

document.addEventListener('DOMContentLoaded', function() {
    const dropdowns = document.querySelectorAll('.relative.mt-2');
  
    dropdowns.forEach(dropdown => {
      const selectButton = dropdown.querySelector('button[type="button"]');
      const selectList = dropdown.querySelector('ul');
      const listItems = selectList.querySelectorAll('[role="option"]');
  
      selectButton.addEventListener('click', function() {
        const expanded = selectButton.getAttribute('aria-expanded') === 'true' || false;
        selectButton.setAttribute('aria-expanded', !expanded);
        selectList.classList.toggle('hidden');
      });
  
      listItems.forEach(item => {
        item.addEventListener('click', function() {
          if (this.closest('#select-list_search')) {
            document.getElementById("search-button").classList.remove('bg-gray-500', 'pointer-events-none');
            document.getElementById("search-button").classList.add('bg-blue-700');
          }
          else if (this.closest('#select-list_export')) {
            document.getElementById("export-map-view-button").classList.remove('bg-gray-500', 'pointer-events-none');
            document.getElementById("export-map-view-button").classList.add('bg-blue-700');
          }
          //activate visualize/search button
          // console.log("entered here");
          if (this.closest('#select-list-bbox')) {
            // console.log("entered inside");
            // console.log(drawToolbar);
            if (drawToolbar) {
              drawToolbar.style.display = 'none';
            }
            // if(drawnItems){
            //   map.removeLayer(drawnItems);
            // }
          }
  
          document.getElementById("formulaHeading").classList.add('hidden'); 
          document.getElementById("formulaHeading-export").classList.add('hidden'); 
  
  
          // Update the button text and image/icon with the selected item's data
          const selectedItemId = item.id;
          const selectedItemText = item.querySelector('.truncate').innerText;
          const selectedItemIcon = item.querySelector('img, i'); // Select either img or i element
  
          // Update button text
          selectButton.querySelector('.truncate').innerText = selectedItemText;
  
          // Update button image/icon
          const buttonIcon = selectButton.querySelector('img, i'); // Select either img or i element
          if (selectedItemIcon.tagName === 'IMG') {
            buttonIcon.src = selectedItemIcon.src;
          } else if (selectedItemIcon.tagName === 'I') {
            buttonIcon.className = selectedItemIcon.className;
          }
  
          // Update the selected class
          listItems.forEach(i => {
            i.classList.remove('bg-indigo-600', 'text-white', 'font-semibold');
            i.querySelector('span').classList.remove('text-white');
          });
          item.classList.add('bg-indigo-600', 'text-white', 'font-semibold');
          item.querySelector('span').classList.add('text-white');
  
          // Show the checkmark for the selected item
          const checkIcon = item.querySelector('svg');
          listItems.forEach(i => i.querySelector('svg').classList.add('hidden'));
          checkIcon.classList.remove('hidden');
  
          // Close the select list
          selectButton.setAttribute('aria-expanded', false);
          selectList.classList.add('hidden');
  
          // Show/Hide content based on the selected option
          const coords = document.getElementById('map-window-content');
          const drawBBoxOption = document.getElementById('draw-bbox-option');
          const uploadBBoxFileOption = document.getElementById('upload-bbox-file-option');
  
          // Hide all sections first
          // coords.classList.add('hidden');
          drawBBoxOption.classList.add('hidden');
          uploadBBoxFileOption.classList.add('hidden');
  
          // Show the corresponding section based on the selected item
          if (selectedItemId === 'map-window-bbox') {
            coords.classList.remove('hidden');
  
            if(Object.keys(drawnItems._layers).length > 0){
              // console.log(drawnItems);
              if(rectangle){
                map.removeLayer(rectangle);
              }
              map.removeLayer(drawnItems);
              export_params_bbox_changed = false;
            }
            //reset bbox html
            export_params.bbox = `${bounds.getWest()},${bounds.getSouth()},${bounds.getEast()},${bounds.getNorth()}`;
            document.getElementById("map-window-content").innerHTML = export_params.bbox;
          } else if (selectedItemId === 'draw-aoi-on-map') {
            // console.log("fired");
            // coords.classList.add('hidden');
            drawBBoxOption.classList.remove('hidden');
            // console.log(Object.keys(highlightedLayer._layers).length > 0);
            if(Object.keys(drawnItems._layers).length > 0){
              // console.log(drawnItems);
              updateDrawnItemBbox(drawnItems);
              map.addLayer(drawnItems);
            }
          } else if (selectedItemId === 'upload-file-bbox') {
            coords.classList.add('hidden');
            uploadBBoxFileOption.classList.remove('hidden');
          }
        });
      });
  
      document.addEventListener('click', function(event) {
        if (!dropdown.contains(event.target)) {
          selectButton.setAttribute('aria-expanded', false);
          selectList.classList.add('hidden');
        }
      });
    });
  });
  
  //if template provided options clicked eg. NDVI, NDWI
  document.querySelectorAll('.template-filters').forEach(function(item) {
      item.addEventListener('click', function() {
          const templateText = item.querySelector('.template-filters-value').getAttribute('value');
          // console.log(templateText); 
          var param;
          //check if dropwn inside export is clicked or search is clicked
          if (this.closest('#select-list_export')) {
            // console.log("yes this is export");
            param = export_params;
          }
          else{
            // console.log("no this is search");
            param = tile_params;
          }
  
        if(templateText == "NDVI"){
          param.formula = "(band2 - band1) / (band2 + band1)";
          param.band1 = 'red';
          param.band2 = 'nir';
        }
        else if(templateText == "NDWI"){
          param.formula = "(band2 - band1) / (band2 + band1)";
          param.band1 = 'nir';
          param.band2 = 'green';
        }
        else if(templateText == "visual"){
          param.formula = "band1";
          param.band1 = 'visual';
          param.band2 = '';
        }
        
      });
  });
  //buttons and filters end


  //loader script start
  function startLoader(divId) {
    const targetDiv = document.getElementById(divId);
    targetDiv.style.position = 'relative';
    if (!targetDiv.querySelector('.html-loader')) {
      const loaderDiv = document.createElement('div');
      loaderDiv.classList.add('html-loader');
      targetDiv.appendChild(loaderDiv);
    }
    targetDiv.querySelector('.html-loader').style.display = 'block'; // Show loader
  }

  // Function to stop the new loader for a specific div
  function stopLoader(divId) {
    const targetDiv = document.getElementById(divId);
    const loader = targetDiv.querySelector('.html-loader');
    if (loader) {
      loader.style.display = 'none'; // Hide loader
    }
  }
  //loader script end


  // Function to handle icon clicks
function handleInfoClick(event) {
  const title = event.target.title;
  // console.log('Info clicked:', title);
  // You can show a tooltip, modal, toast, etc. here
  showMessage('message', 30000, title);
}

// Wait until DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
  const infoIcons = document.querySelectorAll('.info-icons');
  infoIcons.forEach(icon => {
    icon.style.cursor = 'pointer';
    icon.addEventListener('click', handleInfoClick);
  });
});

  
      

