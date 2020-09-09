from plantcv import plantcv as pcv

import logging

logger = logging.getLogger(__name__)

from ipapi.base.ipt_abstract import IptBase
import ipapi.base.ip_common as ipc


class IptPcvBinaryThreshold(IptBase):
    def build_params(self):
        self.add_enabled_checkbox()
        self.add_channel_selector(default_value="h")
        self.add_spin_box(
            name="threshold",
            desc="Threshold value (0-255)",
            default_value=0,
            minimum=0,
            maximum=255,
        )
        self.add_spin_box(
            name="max_value",
            desc="Value to apply above threshold (255 = white)",
            default_value=255,
            minimum=0,
            maximum=255,
        )
        self.add_slider(
            name="median_filter_size",
            desc="Median filter size (odd values only)",
            default_value=0,
            minimum=0,
            maximum=51,
        )
        self.add_combobox(
            name="object_type",
            desc="Keep light or dark object",
            default_value="light",
            values=dict(light="light", dark="dark"),
            hint=""""light" or "dark" (default: "light"). If object is lighter than the background then standard 
            thresholding is done. If object is darker than the background then inverse thresholding is done.""",
        )
        self.add_text_overlay(0)
        self.add_checkbox(
            name="build_mosaic",
            desc="Build mosaic",
            default_value=0,
            hint="If true edges and result will be displayed side by side",
        )
        self.add_color_selector(
            name="background_color",
            desc="Background color",
            default_value="none",
            hint='Color to be used when printing masked image.\n if "None" is selected standard mask will be printed.',
            enable_none=True,
        )

    def process_wrapper(self, **kwargs):
        # Copy here the docstring generated by IPSO Phen
        wrapper = self.init_wrapper(**kwargs)
        if wrapper is None:
            return False

        res = False
        try:
            if self.get_value_of("enabled") == 1:
                img = wrapper.current_image

                threshold = self.get_value_of("threshold")
                max_value = self.get_value_of("max_value")
                median_filter_size = self.get_value_of("median_filter_size")
                median_filter_size = (
                    0 if median_filter_size == 1 else ipc.ensure_odd(median_filter_size)
                )

                c = wrapper.get_channel(
                    img, self.get_value_of("channel"), "", [], False, median_filter_size
                )

                self.result = pcv.threshold.binary(
                    c, threshold, max_value, self.get_value_of("object_type")
                )

                # Write your code here
                wrapper.store_image(self.result, "current_image")
                res = True
            else:
                wrapper.store_image(wrapper.current_image, "current_image")
                res = True
        except Exception as e:
            res = False
            wrapper.error_holder.add_error(
                new_error_text=f'Failed to process {self. name}: "{repr(e)}"',
                new_error_level=35,
                target_logger=logger,
            )
        else:
            pass
        finally:
            return res

    @property
    def name(self):
        return "PCV Binary Threshold"

    @property
    def package(self):
        return "PlantCV"

    @property
    def real_time(self):
        return True

    @property
    def result_name(self):
        return "mask"

    @property
    def output_kind(self):
        return "mask"

    @property
    def use_case(self):
        return ["Threshold", "PlantCV"]

    @property
    def description(self):
        return """Creates a binary image from a gray image based on the threshold values. The object target can be specified as dark or light.
plantcv.threshold.binary(gray_img, threshold, max_value, object_type= light )
returns thresholded/binary image
https://plantcv.readthedocs.io/en/stable/binary_threshold/"""
