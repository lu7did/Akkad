cmake -S . -B build-twins -G Ninja `
  -DPICOSARGON_PICO=ON `
  -DPICO_BOARD=pico2_w `
  -DTWINS=ON `
  -DSTEROIDS=ON

cmake --build build-twins
