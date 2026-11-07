$ArmRoot = Join-Path $PSScriptRoot '..\..\ARM'
$ArmRoot = [IO.Path]::GetFullPath($ArmRoot)
cmake -S "$ArmRoot" -B "$ArmRoot/build-twins" -G Ninja `
  -DPICOSARGON_PICO=ON `
  -DPICO_BOARD=pico2_w `
  -DTWINS=ON `
  -DSTEROIDS=ON

cmake --build "$ArmRoot/build-twins"
