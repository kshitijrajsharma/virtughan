// Function to check if the image is loaded
function checkImageLoaded(imageId, loaderContainer) {
  const img = document.getElementById(imageId);

  // Event listener for when the image loads successfully
  img.addEventListener('load', () => {
    console.log('Image has loaded.');
    stopLoader(loaderContainer);
  });

  // Optional: Event listener for when there's an error loading the image
  img.addEventListener('error', () => {
    console.log('Failed to load the image.');
   
  });

  // Check if the image is already loaded (e.g., from cache)
  if (img.complete && img.naturalHeight !== 0) {
    console.log('Image has already been loaded.');
    
  }
}
document.addEventListener('DOMContentLoaded', (event) => {

  // Preload images
  function preloadImages(images, callback) {
      
      let loadedCount = 0;
      const uid = localStorage.getItem('UID');
    //   console.log("UID: ", uid)

      images.forEach((src, index) => {
          const img = new Image();
          img.src = `static/export/${uid}/${src}`;
          img.onload = () => {
              loadedCount++;
              loadedImages[index] = img;
              if (loadedCount === images.length) {
                  callback();
              }
          };
          img.onerror = () => {
              console.error(`Error loading image: ${src}`);
              loadedCount++;
              if (loadedCount === images.length) {
                  callback();
              }
          };
      });
  }

  // Function to process data
  function processData(data) {
      let imageDatePairs = [];
      for (const [key, value] of Object.entries(data)) {
          if (key.endsWith('.png')) {
              const dateMatch = key.match(/\d{8}/);
              if (dateMatch) {
                  const dateStr = dateMatch[0];
                  const formattedDate = `${dateStr.slice(0, 4)}-${dateStr.slice(4, 6)}-${dateStr.slice(6, 8)}`;
                  imageDatePairs.push({ image: key, date: new Date(formattedDate) });
              }
          }
      }
      // Sort by date
      imageDatePairs.sort((a, b) => a.date - b.date);
      // Separate sorted images and dates
      pngImages = imageDatePairs.map(pair => pair.image);
      dates = imageDatePairs.map(pair => pair.date.toISOString().split('T')[0]);
  }
    // Function to open the modal and display images based on checkbox selections
  function openModal() {
      const operationChecked = document.getElementById('operation').checked;
      const timeSeriesChecked = document.getElementById('timeSeries').checked;
      document.getElementById("operationTabButton").click();

      const uid = localStorage.getItem('UID');
      
      if (operationChecked && !timeSeriesChecked) {
          startLoader("operationContainer");
          // Display single image for operation
          document.getElementById('operationContainer').classList.remove('hidden');
          document.getElementById('timeSeriesContainer').classList.add('hidden');
          document.getElementById('timeSeriesTrendContainer').classList.add('hidden');
          document.getElementById('tabs').classList.add('hidden');
          document.getElementById('operationImageView').src = 'static/export/'+uid+'/custom_band_output_aggregate_colormap.png';
          document.getElementById('operationDateDisplay').textContent = '';
          document.getElementById('timeSliderModal').classList.remove('hidden');
          
          checkImageLoaded("operationImageView", "operationContainer"); //remove loader after image is loaded.

      } else if (timeSeriesChecked && !operationChecked) {
          startLoader("timeSeriesContainer");
          startLoader("trendImageContainer");
          // Display time series
          document.getElementById('operationContainer').classList.add('hidden');
          document.getElementById('timeSeriesContainer').classList.remove('hidden');
          document.getElementById('timeSeriesTrendContainer').classList.remove('hidden');
          document.getElementById('tabs').classList.remove('hidden');
          document.getElementById('operationTabButton').classList.add('hidden');
          document.getElementById('timeSliderModal').classList.remove('hidden');
          document.getElementById('trendImageView').src = 'static/export/'+uid+'/values_over_time.png';

          // Fetch data
          const urlLists = '/list-files?uid='+uid;
          fetch(urlLists, { method: 'GET' })
              .then(response => response.json())
              .then(data => {
                  processData(data);
                  preloadImages(pngImages, () => {
                      initializeSlider();
                      // Load the first image at start
                      if (loadedImages.length > 0 && dates.length > 0) {
                          document.getElementById('timeSeriesImageContainer').innerHTML = '';
                          document.getElementById('timeSeriesImageContainer').appendChild(loadedImages[0]);
                          document.getElementById('dateDisplay').textContent = new Date(dates[0]).toLocaleDateString();
                          // changeImage();
                      }
                      stopLoader("timeSeriesContainer");
                  });
              })
              .catch((error) => {
                  console.error('Error:', error);
              });

              checkImageLoaded("trendImageView", "trendImageContainer");


      } else if (operationChecked && timeSeriesChecked) {
          startLoader("operationContainer");
          startLoader("timeSeriesContainer");
          startLoader("trendImageContainer");
          // Show tabs for both operation and time series
          document.getElementById('tabs').classList.remove('hidden');
          document.getElementById('operationContainer').classList.remove('hidden');
          document.getElementById('timeSeriesContainer').classList.add('hidden');
          document.getElementById('timeSeriesTrendContainer').classList.add('hidden');
          document.getElementById('timeSliderModal').classList.remove('hidden');
          // Load operation image initially
          document.getElementById('operationImageView').src = 'static/export/'+uid+'/custom_band_output_aggregate_colormap.png';
          document.getElementById('operationDateDisplay').textContent = '';

          document.getElementById('trendImageView').src = 'static/export/'+uid+'/values_over_time.png';

          // Fetch data for time series
          const urlLists = '/list-files?uid='+uid;
          fetch(urlLists, { method: 'GET' })
              .then(response => response.json())
              .then(data => {
                  processData(data);
                  preloadImages(pngImages, () => {
                      initializeSlider();
                      // Load the first image at start
                      if (loadedImages.length > 0 && dates.length > 0) {
                          document.getElementById('timeSeriesImageContainer').innerHTML = '';
                          document.getElementById('timeSeriesImageContainer').appendChild(loadedImages[0]);
                          document.getElementById('dateDisplay').textContent = new Date(dates[0]).toLocaleDateString();
                          // changeImage();
                      }
                      stopLoader("timeSeriesContainer");
                  });
              })
              .catch((error) => {
                  console.error('Error:', error);
              });
        
          checkImageLoaded("operationImageView", "operationContainer");
          checkImageLoaded("trendImageView", "trendImageContainer");  
      }
      
  }

  // Function to switch tabs
  function switchTab(tab) {
      if (tab === 'operation') {
          document.getElementById('operationContainer').classList.remove('hidden');
          document.getElementById('timeSeriesContainer').classList.add('hidden');
          document.getElementById('timeSeriesTrendContainer').classList.add('hidden');
          // document.getElementById('operationImageView').src = 'static/export/'+uid+'/custom_band_output_aggregate_colormap.png';
          document.getElementById('operationDateDisplay').textContent = '';
      } else if (tab === 'timeSeries') {
          document.getElementById('operationContainer').classList.add('hidden');
          document.getElementById('timeSeriesContainer').classList.remove('hidden');
          document.getElementById('timeSeriesTrendContainer').classList.add('hidden');
          // Show the first time series image and date
          if (loadedImages.length > 0 && dates.length > 0) {
              document.getElementById('timeSeriesImageContainer').innerHTML = '';
              document.getElementById('timeSeriesImageContainer').appendChild(loadedImages[0]);
              document.getElementById('dateDisplay').textContent = new Date(dates[0]).toLocaleDateString();
          }
      }
      else if (tab === 'timeSeriesTrend'){
        document.getElementById('operationContainer').classList.add('hidden');
        document.getElementById('timeSeriesContainer').classList.add('hidden');
        document.getElementById('timeSeriesTrendContainer').classList.remove('hidden');
      }
  }

    // Function to close the modal
  function closeModal() {
      document.getElementById('timeSliderModal').classList.add('hidden');
      stopPlay();
  }

  // Function to change the image based on the slider value
  function changeImage() {
      const slider = document.getElementById('dateRangeSlider');
      const index = slider.value;
      const selectedDate = dates[index];
      const selectedImage = loadedImages[index];
      document.getElementById('timeSeriesImageContainer').innerHTML = '';
      document.getElementById('timeSeriesImageContainer').appendChild(selectedImage);
      document.getElementById('dateDisplay').textContent = new Date(selectedDate).toLocaleDateString();
  }

  // Function to play the slider automatically
  function playSlider() {
      if (isPlaying) return;
      isPlaying = true;
      document.getElementById('playIcon').classList.add('hidden');
      document.getElementById('pauseIcon').classList.remove('hidden');
      playInterval = setInterval(() => {
          const slider = document.getElementById('dateRangeSlider');
          if (slider.value >= dates.length - 1) {
              slider.value = 0;
          } else {
              slider.value = parseInt(slider.value) + 1;
          }
          changeImage();
      }, 1500); // Adjust the interval
  }

  // Function to stop the automatic play
  function stopPlay() {
      if (!isPlaying) return;
      isPlaying = false;
      clearInterval(playInterval);
      document.getElementById('playIcon').classList.remove('hidden');
      document.getElementById('pauseIcon').classList.add('hidden');
  }

  // Function to toggle play/pause
  function togglePlayPause() {
      if (isPlaying) {
          stopPlay();
      } else {
          playSlider();
      }
  }

  // Function to initialize the slider and markers
  function initializeSlider() {
      const slider = document.getElementById('dateRangeSlider');
      slider.max = dates.length - 1;
      slider.step = 1;
      // Event listeners for slider and play/pause button
      slider.addEventListener('input', changeImage);
      document.getElementById('playPauseButton').addEventListener('click', togglePlayPause);
      // Initialize markers for the slider
      const markersContainer = document.querySelector('.slider-markers');
      markersContainer.innerHTML = dates.map((date, index) => {
          if (index % 2 === 0) { // Adjust spacing by showing every 2nd date marker
              const dateObj = new Date(date);
              const month = dateObj.toLocaleString('default', { month: 'short' });
              const day = dateObj.getDate();
              return `<span>${month} ${day}</span>`;
          } else {
              return `<span></span>`;
          }
      }).join('');
  }

  // Event listeners for modal
  document.getElementById('view-result-image').addEventListener('click', openModal);
  document.querySelector('.close').addEventListener('click', closeModal); 
  document.getElementById('operationTabButton').addEventListener('click', () => switchTab('operation')); 
  document.getElementById('timeSeriesTabButton').addEventListener('click', () => switchTab('timeSeries')); 
  document.getElementById('timeSeriesTrendTabButton').addEventListener('click', () => switchTab('timeSeriesTrend')); 
  // Optional: Close the modal when clicking outside of it 
  window.addEventListener('click', (event) => { 
    if (event.target === document.getElementById('timeSliderModal')) { 
      closeModal(); 
    } 
  }); 
});

document.addEventListener('DOMContentLoaded', function() {
    const tabs = document.querySelectorAll('.tab-button');

    tabs.forEach(tab => {
        tab.addEventListener('click', function() {
            tabs.forEach(t => t.classList.remove('active', 'bg-blue-500', 'text-white'));
            tabs.forEach(t => t.classList.add('bg-gray-200', 'text-blue-500'));
            this.classList.add('active', 'bg-blue-500', 'text-white');
            this.classList.remove('bg-gray-200', 'text-blue-500');
        });
    });
});