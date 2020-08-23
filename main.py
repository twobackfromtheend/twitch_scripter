from pathlib import Path

from deepspeech import Model

model_folder = Path(__file__).parent / "models"

pbmm_path = list(model_folder.glob("*.pbmm"))[0]
scorer_path = list(model_folder.glob("*.scorer"))[0]

if __name__ == '__main__':
    ds = Model(str(pbmm_path))

