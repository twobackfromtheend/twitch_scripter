#!/usr/bin/env bash

version="0.8.2"

cd models
curl -LO https://github.com/mozilla/DeepSpeech/releases/download/v${version}/deepspeech-${version}-models.pbmm
curl -LO https://github.com/mozilla/DeepSpeech/releases/download/v${version}/deepspeech-${version}-models.scorer
