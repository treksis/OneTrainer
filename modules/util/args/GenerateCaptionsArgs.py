import argparse
from typing import Any

from modules.util.args.BaseArgs import BaseArgs
from modules.util.enum.DataType import DataType
from modules.util.enum.GenerateCaptionsModel import GenerateCaptionsModel


class GenerateCaptionsArgs(BaseArgs):
    model: GenerateCaptionsModel
    sample_dir: str
    initial_caption: str
    mode: str
    device: str
    dtype: DataType

    def __init__(self, data: list[(str, Any, type, bool)]):
        super(GenerateCaptionsArgs, self).__init__(data)

    @staticmethod
    def parse_args() -> 'GenerateCaptionsArgs':
        parser = argparse.ArgumentParser(description="One Trainer Generate Captions Script.")

        # @formatter:off

        parser.add_argument("--model", type=GenerateCaptionsModel, required=True, dest="model", help="The model to use when generating captions")
        parser.add_argument("--sample-dir", type=str, required=True, dest="sample_dir", help="Directory where samples are located")
        parser.add_argument("--initial-caption", type=str, default='', required=False, dest="initial_caption", help="An initial caption to start generating from")
        parser.add_argument("--mode", type=str, default='fill', required=False, dest="mode", help="Either replace, fill, add or subtract")
        parser.add_argument("--device", type=str, required=False, default="cuda", dest="device", help="The device to use for calculations")
        parser.add_argument("--dtype", type=DataType, required=False, default=DataType.FLOAT_16, dest="dtype", help="The data type to use for weights during calculations", choices=list(DataType))

        # @formatter:on

        args = GenerateCaptionsArgs.default_values()
        args.from_dict(vars(parser.parse_args()))
        return args

    @staticmethod
    def default_values():
        data = []

        data.append(("model", GenerateCaptionsModel.BLIP, GenerateCaptionsModel, False))
        data.append(("sample_dir", "", str, False))
        data.append(("initial_caption", "", str, False))
        data.append(("mode", "fill", str, False))
        data.append(("device", "cuda", str, False))
        data.append(("dtype", DataType.FLOAT_16, DataType, False))

        return GenerateCaptionsArgs(data)
