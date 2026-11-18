#!/bin/sh
# Builds libADLMIDI's WAV-only player (OPL3 FM synth) into build/libADLMIDI, for tools/music.py.
set -e
cd "$(dirname "$0")/.."
mkdir -p build
[ -d build/libADLMIDI ] || git clone -q --depth 1 https://github.com/Wohlstand/libADLMIDI.git build/libADLMIDI
cd build/libADLMIDI
# the WAV-only player still asks for ALSA on Linux; it doesn't need it
sed -i 's/if(UNIX AND NOT APPLE AND NOT MIDIPLAY_PREFER_SDL)$/if(UNIX AND NOT APPLE AND NOT MIDIPLAY_PREFER_SDL AND NOT MIDIPLAY_WAVE_ONLY)/' utils/midiplay/CMakeLists.txt
mkdir -p build && cd build
cmake .. -DCMAKE_BUILD_TYPE=Release -DWITH_MIDIPLAY=ON -DMIDIPLAY_WAVE_ONLY=ON -DUSE_NUKED_EMULATOR=ON -DlibADLMIDI_SHARED=OFF > /dev/null
make -j8 adlmidiplay > /dev/null
echo "built $(pwd)/adlmidiplay"
