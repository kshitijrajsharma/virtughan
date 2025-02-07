const colorScales = { 
    'RdYlGn': d3.interpolateRdYlGn,
    'BrBG': d3.interpolateBrBG,
    'PrGn': d3.interpolatePRGn,
    'PiYG': d3.interpolatePiYG,
    'PuOr': d3.interpolatePuOr,
    'RdBu': d3.interpolateRdBu,
    'RdGy': d3.interpolateRdGy,
    'RdYlBu': d3.interpolateRdYlBu,
    'Spectral': d3.interpolateSpectral,
    'Viridis': d3.interpolateViridis,
    'Inferno': d3.interpolateInferno,
    'Magma': d3.interpolateMagma,
    'Plasma': d3.interpolatePlasma,
    'Cividis': d3.interpolateCividis,
    'Blues': d3.interpolateBlues,
    'Greens': d3.interpolateGreens,
    'Greys': d3.interpolateGreys,
    'Oranges': d3.interpolateOranges,
    'Purples': d3.interpolatePurples,
    'Reds': d3.interpolateReds
};

function createColorOptions() {
    const ul = document.querySelector("#PaletteSelect ul");
    ul.innerHTML = ''; // Clear existing options

    Object.keys(colorScales).forEach((scaleName, index) => {
        const colorScale = colorScales[scaleName];
        const li = document.createElement('li');
        li.className = "flex items-center px-4 py-2 cursor-pointer hover:bg-gray-100";
        li.dataset.scale = scaleName; // Add data attribute
        li.value = scaleName; // Set value attribute
        li.onclick = () => selectColor(colorScale, scaleName);
        
        for (let i = 0; i <= 1; i += 0.1) {
            const colorBox = document.createElement('span');
            colorBox.className = "color-option";
            colorBox.style.backgroundColor = colorScale(i);
            colorBox.style.width = "10%";
            li.appendChild(colorBox);
        }
        ul.appendChild(li);

        // Set the first option as default selected
        if (index === 0) {
            selectColor(colorScale, scaleName);
        }
    });
}

function toggleDropdown() {
    const menu = document.getElementById("PaletteSelect");
    menu.classList.toggle("hidden");
}

function selectColor(colorScale, scaleName) {
      const button = document.getElementById("PaletteSelectButton");
      button.innerHTML = ''; // Clear existing content
      const container = document.createElement('div');
      container.className = 'flex'; // Use Tailwind flex class to arrange items horizontally
      for (let i = 0; i <= 1; i += 0.1) {
          const colorBox = document.createElement('span');
          colorBox.className = "color-option inline-block";
          colorBox.style.backgroundColor = colorScale(i);
          colorBox.style.width = "10%";
          container.appendChild(colorBox);
      }
      button.appendChild(container);
      button.dataset.selectedScale = scaleName; // Store selected scale name
      button.value = scaleName; // Add value to button
      toggleDropdown();

      // console.log("onchange");
      // Call updateRasterColor function with the selected palette
      updateRasterColor(scaleName);
      // Call updateLegend with the appropriate palette
      updateLegend(getSelectedPalette());

  }


function getSelectedPalette() {
    const button = document.getElementById("PaletteSelectButton");
    if(button.value == ''){return 'RdYlGn'} else{
      return button.value;
    }
     
}

document.addEventListener("click", function(event) {
    const dropdown = document.getElementById("PaletteSelectButton");
    const menu = document.getElementById("PaletteSelect");
    if (!dropdown.contains(event.target)) {
        menu.classList.add("hidden");
    }
});

window.onload = createColorOptions; // Populate dropdown options on page load

// Function to update the color for multi-band rasters
// Function to update the color for single-band and multi-band rasters
function updateColor(values, scaleName) {
const colorScale = colorScales[scaleName]; // Get the color scale function
const scale = d3.scaleSequential(colorScale)
    .domain([min, max]);

// console.log(values.length);
if (values.length === 1) {
    // Single-band raster
    return scale(values[0]);
} else {
    // Multi-band raster (e.g., RGB)
    const r = Math.round((values[0] - min) / (max - min) * 255);
    const g = Math.round((values[1] - min) / (max - min) * 255);
    const b = Math.round((values[2] - min) / (max - min) * 255);
    // console.log(r);

    // Ensure the values are within [0, 255] range
    const clamp = value => Math.max(0, Math.min(255, value));
    // console.log(clamp(r));

    document.getElementById("colorPalettes").classList.add("hidden");

    return `rgb(${clamp(r)}, ${clamp(g)}, ${clamp(b)})`;
}
}


// Function to process raster data and discard NaN values
function processRasterData(rasterData) {
    const noDataValue = -9999; // NaN value in data
    let validValues = [];

    rasterData.values.forEach(val => {
      val.forEach(row => {
        row.forEach(value => {
            if (value !== noDataValue) {
                validValues.push(value);
            }
        });
    });
  });

    return validValues;
}