from typing import Iterable

import torch
from torch.nn import Parameter

from modules.model.StableDiffusionXLModel import StableDiffusionXLModel
from modules.modelSetup.BaseStableDiffusionXLSetup import BaseStableDiffusionXLSetup
from modules.util import create
from modules.util.TrainProgress import TrainProgress
from modules.util.args.TrainArgs import TrainArgs


class StableDiffusionXLFineTuneSetup(BaseStableDiffusionXLSetup):
    def __init__(
            self,
            train_device: torch.device,
            temp_device: torch.device,
            debug_mode: bool,
    ):
        super(StableDiffusionXLFineTuneSetup, self).__init__(
            train_device=train_device,
            temp_device=temp_device,
            debug_mode=debug_mode,
        )

    def create_parameters(
            self,
            model: StableDiffusionXLModel,
            args: TrainArgs,
    ) -> Iterable[Parameter]:
        params = list()

        if args.train_text_encoder:
            params += list(model.text_encoder_1.parameters())
            params += list(model.text_encoder_2.parameters())

        if args.train_unet:
            params += list(model.unet.parameters())

        return params

    def create_parameters_for_optimizer(
            self,
            model: StableDiffusionXLModel,
            args: TrainArgs,
    ) -> Iterable[Parameter] | list[dict]:
        param_groups = list()

        if args.train_text_encoder:
            lr = args.text_encoder_learning_rate if args.text_encoder_learning_rate is not None else args.learning_rate
            param_groups.append({
                'params': model.text_encoder_1.parameters(),
                'lr': lr,
                'initial_lr': lr,
            })
            param_groups.append({
                'params': model.text_encoder_2.parameters(),
                'lr': lr,
                'initial_lr': lr,
            })

        if args.train_unet:
            lr = args.unet_learning_rate if args.unet_learning_rate is not None else args.learning_rate
            param_groups.append({
                'params': model.unet.parameters(),
                'lr': lr,
                'initial_lr': lr,
            })

        return param_groups

    def setup_model(
            self,
            model: StableDiffusionXLModel,
            args: TrainArgs,
    ):
        train_text_encoder = args.train_text_encoder and (model.train_progress.epoch < args.train_text_encoder_epochs)
        model.text_encoder_1.requires_grad_(train_text_encoder)
        model.text_encoder_2.requires_grad_(train_text_encoder)

        train_unet = args.train_unet and (model.train_progress.epoch < args.train_unet_epochs)
        model.unet.requires_grad_(train_unet)

        model.vae.requires_grad_(False)

        model.optimizer = create.create_optimizer(
            self.create_parameters_for_optimizer(model, args), model.optimizer_state_dict, args
        )
        del model.optimizer_state_dict

        model.ema = create.create_ema(
            self.create_parameters(model, args), model.ema_state_dict, args
        )
        del model.ema_state_dict

        self.setup_optimizations(model, args)

    def setup_eval_device(
            self,
            model: StableDiffusionXLModel
    ):
        model.text_encoder_1.to(self.train_device)
        model.text_encoder_2.to(self.train_device)
        model.vae.to(self.train_device)
        model.unet.to(self.train_device)

        model.text_encoder_1.eval()
        model.text_encoder_2.eval()
        model.vae.eval()
        model.unet.eval()

    def setup_train_device(
            self,
            model: StableDiffusionXLModel,
            args: TrainArgs,
    ):
        model.text_encoder_1.to(self.train_device)
        model.text_encoder_2.to(self.train_device)
        model.vae.to(self.temp_device)
        model.unet.to(self.train_device)

        if args.train_text_encoder:
            model.text_encoder_1.train()
            model.text_encoder_2.train()
        else:
            model.text_encoder_1.eval()
            model.text_encoder_2.eval()

        model.vae.train()
        model.unet.train()

    def after_optimizer_step(
            self,
            model: StableDiffusionXLModel,
            args: TrainArgs,
            train_progress: TrainProgress
    ):
        train_text_encoder = args.train_text_encoder and (model.train_progress.epoch < args.train_text_encoder_epochs)
        model.text_encoder_1.requires_grad_(train_text_encoder)
        model.text_encoder_2.requires_grad_(train_text_encoder)

        train_unet = args.train_unet and (model.train_progress.epoch < args.train_unet_epochs)
        model.unet.requires_grad_(train_unet)
