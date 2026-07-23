import importlib.machinery
import importlib.util
import io
import json
import tempfile
import threading
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from PIL import Image, features


ROOT = Path(__file__).resolve().parents[1]
LOADER = importlib.machinery.SourceFileLoader(
    "transparentor_app",
    str(ROOT / "Transparentor.pyw"),
)
SPEC = importlib.util.spec_from_loader(LOADER.name, LOADER)
APP = importlib.util.module_from_spec(SPEC)
LOADER.exec_module(APP)


class Value:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value


class ReleaseSmokeTests(unittest.TestCase):
    def test_release_identity_and_default_model(self):
        self.assertEqual(APP.APP_VERSION, "1.1.0")
        self.assertEqual(APP.PROJECT_FORMAT_VERSION, 4)
        self.assertEqual(APP.DEFAULT_AI_MODEL, APP.FUSION_AI_MODEL)
        self.assertIn(APP.DEFAULT_AI_MODEL, APP.AI_MODEL_INFO)
        self.assertEqual(
            APP._ai_component_models(APP.FUSION_AI_MODEL),
            ("birefnet-massive", "isnet-general-use"),
        )

    def test_header_brand_mark_uses_the_application_icon(self):
        brand_mark = APP._build_brand_mark_image(
            ROOT / "transparentoricon.ico",
            36,
        )

        self.assertEqual(brand_mark.mode, "RGBA")
        self.assertEqual(brand_mark.size, (36, 36))
        self.assertEqual(brand_mark.getpixel((0, 0))[3], 0)
        self.assertGreater(brand_mark.getpixel((18, 18))[3], 240)
        self.assertGreater(
            len(brand_mark.convert("RGB").getcolors(maxcolors=36 * 36)),
            32,
        )

    def test_windows_application_identity_is_explicit(self):
        calls = []

        class Shell32:
            @staticmethod
            def SetCurrentProcessExplicitAppUserModelID(app_id):
                calls.append(app_id)
                return 0

        self.assertTrue(APP._set_windows_app_identity(Shell32()))
        self.assertEqual(calls, [APP.WINDOWS_APP_USER_MODEL_ID])
        self.assertEqual(
            APP.WINDOWS_APP_USER_MODEL_ID,
            f"Transparentor.Desktop.{APP.APP_VERSION}",
        )

    def test_background_classifier_separates_chroma_from_dark_artwork(self):
        import numpy as np

        dark = np.full((8, 8, 3), (2, 8, 24), dtype=np.uint8)
        green = np.full((8, 8, 3), (0, 255, 0), dtype=np.uint8)
        cyan = np.full((8, 8, 3), (0, 255, 255), dtype=np.uint8)
        neutral = np.full((8, 8, 3), (210, 210, 210), dtype=np.uint8)

        self.assertEqual(APP._classify_uniform_background(dark)["kind"], "dark")
        self.assertEqual(APP._classify_uniform_background(green)["kind"], "chroma")
        self.assertEqual(APP._classify_uniform_background(cyan)["kind"], "chroma")
        self.assertEqual(APP._classify_uniform_background(neutral)["kind"], "uniform")

    def test_background_classifier_recognizes_gradient_chroma_perimeter(self):
        import numpy as np

        gradient = np.zeros((80, 60, 3), dtype=np.uint8)
        for row in range(80):
            green = 80 + row
            gradient[row, :, :] = (5, green, 12)

        profile = APP._classify_uniform_background(gradient)

        self.assertEqual(profile["kind"], "chroma")
        self.assertTrue(profile["is_gradient_chroma"])
        self.assertGreater(profile["border_screen_fraction"], 0.95)

    def test_background_classifier_rejects_inconsistent_colored_perimeter(self):
        import numpy as np

        varied = np.full((80, 60, 3), (5, 130, 12), dtype=np.uint8)
        varied[:4, ::2] = (160, 30, 20)
        varied[-4:, 1::2] = (25, 45, 160)
        varied[:, :4:2] = (150, 35, 25)
        varied[:, -4::2] = (30, 40, 155)

        profile = APP._classify_uniform_background(varied)

        self.assertFalse(profile["is_gradient_chroma"])
        self.assertNotEqual(profile["kind"], "chroma")

    def test_gradient_chroma_refinement_preserves_cyan_and_caps_green(self):
        import numpy as np

        rgb = np.zeros((9, 11, 3), dtype=np.float32)
        rgb[:, :, 0] = 8.0
        rgb[:, :, 1] = np.linspace(90.0, 210.0, 11)[None, :]
        rgb[:, :, 2] = 14.0
        rgb[4, 4] = (20.0, 190.0, 185.0)
        rgb[4, 5] = (80.0, 200.0, 200.0)
        alpha = np.full((9, 11), 0.7, dtype=np.float32)

        refined, key_alpha = APP._refine_gradient_chroma_alpha(
            rgb,
            alpha,
            1,
        )

        self.assertEqual(float(refined[0, 0]), 0.0)
        self.assertEqual(float(refined[8, 10]), 0.0)
        self.assertAlmostEqual(float(refined[4, 4]), 0.7, places=5)
        self.assertAlmostEqual(float(refined[4, 5]), 0.7, places=5)
        self.assertGreater(float(key_alpha[4, 4]), 0.90)

    def test_gradient_chroma_foreground_reconstruction_restores_color(self):
        import numpy as np

        rgb = np.full((9, 11, 3), (8.0, 150.0, 14.0), dtype=np.float32)
        # A translucent purple sample composited over the same green screen.
        rgb[4, 5] = (100.0, 120.0, 150.0)
        alpha = np.zeros((9, 11), dtype=np.float32)
        alpha[4, 5] = 0.5

        reconstructed = APP._reconstruct_gradient_chroma_foreground(
            rgb,
            alpha,
            1,
            strength=1.0,
        )

        self.assertGreater(reconstructed[4, 5, 0], rgb[4, 5, 0])
        self.assertGreater(reconstructed[4, 5, 2], rgb[4, 5, 2])
        self.assertLessEqual(
            reconstructed[4, 5, 1],
            max(rgb[4, 5, 0], rgb[4, 5, 2]),
        )
        self.assertTrue(np.allclose(reconstructed[0, 0], rgb[0, 0]))

    def test_heavy_uses_conservative_gradient_chroma_refinement(self):
        import numpy as np

        rgb = np.zeros((32, 32, 3), dtype=np.uint8)
        for row in range(32):
            rgb[row, :, :] = (5, 90 + row * 3, 12)
        rgb[12:20, 12:20] = (50, 190, 185)
        source = Image.fromarray(rgb, "RGB").convert("RGBA")
        mask = Image.new("L", source.size, 102)
        app = object.__new__(APP.TransparentorApp)
        app.ai_model_var = Value("birefnet-massive")
        app.protected_mask = set()

        result = app._apply_refined_ai_remove(
            source,
            {
                "model_name": "birefnet-massive",
                "ai_mask": mask,
                "tol": 20.0,
                "soft": 10.0,
                "force_ai_only": True,
                "is_batch": True,
            },
        )
        alpha = np.asarray(result.getchannel("A"), dtype=np.float32)

        self.assertLess(float(alpha[0, 0]), 5.0)
        self.assertGreater(float(alpha[15, 15]), 90.0)
        self.assertLess(float(alpha[15, 15]), 120.0)
        self.assertLess(float(alpha.max()), 130.0)

    def test_isnet_backed_modes_use_dark_background_recovery(self):
        self.assertTrue(APP._uses_dark_background_recovery("isnet-general-use"))
        self.assertFalse(APP._uses_dark_background_recovery("birefnet-massive"))
        self.assertTrue(
            APP._uses_dark_background_recovery(APP.FUSION_AI_MODEL)
        )

    def test_ai_refinement_policy_matches_each_model_role(self):
        self.assertEqual(
            APP._ai_refinement_policy("isnet-general-use"),
            "user",
        )
        self.assertEqual(
            APP._ai_refinement_policy("birefnet-massive"),
            "pure",
        )
        self.assertEqual(
            APP._ai_refinement_policy(APP.FUSION_AI_MODEL),
            "adaptive",
        )

    def test_lightweight_recovers_dark_uniform_background_interior_alpha(self):
        import numpy as np

        rgb = np.full((32, 32, 3), (1, 3, 13), dtype=np.uint8)
        rgb[8:24, 8:24] = (85, 135, 205)
        source = Image.fromarray(rgb, "RGB").convert("RGBA")
        mask = Image.new("L", source.size, 0)
        mask_array = np.zeros((32, 32), dtype=np.uint8)
        mask_array[8:24, 8:24] = 48
        mask = Image.fromarray(mask_array, "L")

        app = object.__new__(APP.TransparentorApp)
        app.ai_model_var = Value("isnet-general-use")
        app.protected_mask = set()
        action = {
            "model_name": "isnet-general-use",
            "ai_mask": mask,
            "tol": 20.0,
            "soft": 10.0,
            "force_ai_only": False,
            "is_batch": True,
        }

        recovered = app._apply_refined_ai_remove(source, action)
        recovered_alpha = np.asarray(recovered.getchannel("A"))

        pure_ai = app._apply_refined_ai_remove(
            source,
            {**action, "force_ai_only": True},
        )
        pure_alpha = np.asarray(pure_ai.getchannel("A"))

        self.assertGreater(float(recovered_alpha[16, 16]), 220.0)
        self.assertLess(float(recovered_alpha[0, 0]), 5.0)
        self.assertGreater(
            float(recovered_alpha[16, 16]),
            float(pure_alpha[16, 16]) + 150.0,
        )

    def test_fusion_uses_isnet_boundary_and_birefnet_supported_dark_interior(self):
        import numpy as np

        rgb = np.full((16, 16, 3), (2, 8, 24), dtype=np.uint8)
        rgb[6:10, 6:10] = (150, 210, 255)
        rgb[2:4, 12:14] = (220, 245, 255)
        heavy = np.zeros((16, 16), dtype=np.float32)
        heavy[6:10, 6:10] = 0.92
        light = heavy.copy()
        light[2:4, 12:14] = 0.78

        fused = APP._fuse_ai_mask_arrays(rgb, heavy, light)

        self.assertTrue(np.all(fused >= light))
        self.assertGreater(float(fused[2:4, 12:14].mean()), 0.50)
        self.assertGreaterEqual(float(fused[7, 7]), float(light[7, 7]))

    def test_fusion_rejects_isnet_only_pixels_matching_chroma_screen(self):
        import numpy as np

        rgb = np.full((12, 12, 3), (0, 255, 0), dtype=np.uint8)
        rgb[4:8, 4:8] = (235, 235, 245)
        heavy = np.zeros((12, 12), dtype=np.float32)
        heavy[4:8, 4:8] = 0.95
        light = heavy.copy()
        light[1:3, 1:3] = 0.85

        fused = APP._fuse_ai_mask_arrays(rgb, heavy, light)

        self.assertLess(float(fused[1:3, 1:3].max()), 0.01)
        self.assertTrue(np.all(fused >= heavy))

    def test_model_change_releases_sessions_the_new_mode_cannot_use(self):
        class Session:
            def __init__(self):
                self.inner_session = object()

        app = object.__new__(APP.TransparentorApp)
        app.ai_session_lock = threading.Lock()
        app.ai_progress_active = False
        heavy = Session()
        light = Session()
        app.ai_sessions = {
            "birefnet-massive": heavy,
            "isnet-general-use": light,
        }

        app._release_unused_ai_sessions("birefnet-massive")

        self.assertEqual(app.ai_sessions, {"birefnet-massive": heavy})
        self.assertIsNone(light.inner_session)

    def test_fusion_sessions_run_sequentially_and_are_released(self):
        events = []

        class Session:
            def __init__(self, model_name):
                self.model_name = model_name
                self.inner_session = object()

        class Ort:
            @staticmethod
            def get_available_providers():
                return ["CPUExecutionProvider"]

        app = object.__new__(APP.TransparentorApp)
        app._shutdown_event = threading.Event()
        app.ai_session_lock = threading.Lock()
        app.ai_sessions = {}
        app._record_ai_inference_duration = mock.Mock()

        def new_session(model_name, providers):
            events.append(("create", model_name, tuple(app.ai_sessions)))
            return Session(model_name)

        def remove(image, session, only_mask):
            events.append(("infer", session.model_name, tuple(app.ai_sessions)))
            return Image.new("L", image.size, 192)

        mask, _duration = app._run_ai_selection_mask(
            Image.new("RGB", (8, 8), "black"),
            APP.FUSION_AI_MODEL,
            remove,
            new_session=new_session,
            ort=Ort,
        )

        self.assertEqual(mask.size, (8, 8))
        self.assertEqual(app.ai_sessions, {})
        self.assertEqual(
            events,
            [
                ("create", "birefnet-massive", ()),
                ("infer", "birefnet-massive", ("birefnet-massive",)),
                ("create", "isnet-general-use", ()),
                ("infer", "isnet-general-use", ("isnet-general-use",)),
            ],
        )

    def test_heavy_session_is_released_when_inference_raises(self):
        class Session:
            def __init__(self):
                self.inner_session = object()

        class Ort:
            @staticmethod
            def get_available_providers():
                return ["CPUExecutionProvider"]

        app = object.__new__(APP.TransparentorApp)
        app._shutdown_event = threading.Event()
        app.ai_session_lock = threading.Lock()
        app.ai_sessions = {}
        app._record_ai_inference_duration = mock.Mock()
        session = Session()

        with self.assertRaisesRegex(RuntimeError, "inference failed"):
            app._run_ai_selection_mask(
                Image.new("RGB", (4, 4), "black"),
                "birefnet-massive",
                lambda *_args, **_kwargs: (_ for _ in ()).throw(
                    RuntimeError("inference failed")
                ),
                new_session=lambda *_args, **_kwargs: session,
                ort=Ort,
            )

        self.assertEqual(app.ai_sessions, {})
        self.assertIsNone(session.inner_session)

    def test_modern_rail_icon_set_renders_every_glyph(self):
        icon_names = (
            "image",
            "clipboard",
            "save",
            "discard",
            "folder",
            "project",
            "undo",
            "redo",
            "crop",
            "lasso",
            "clear",
            "help",
        )
        for icon_name in icon_names:
            with self.subTest(icon=icon_name):
                image = Image.new("RGBA", (88, 88), (0, 0, 0, 0))
                APP._draw_button_icon(
                    APP.ImageDraw.Draw(image),
                    icon_name,
                    88,
                    88,
                    2,
                    "#E8ECF4",
                )
                visible_pixels = sum(value > 0 for value in image.getchannel("A").tobytes())
                self.assertGreater(visible_pixels, 80)

    def test_ai_progress_stage_mapping_and_learned_duration(self):
        app = object.__new__(APP.TransparentorApp)
        app.ai_progress_item_base = 25.0
        app.ai_progress_item_span = 25.0
        app.ai_progress_target = 25.0
        app.ai_progress_stage = ""
        app.ai_progress_stage_started = None
        app.ai_progress_stage_expected = None
        app.ai_progress_after_id = object()
        app.ai_duration_estimates = {"birefnet-massive": 30.0}
        app._draw_ai_progress = mock.Mock()
        app._schedule_ai_progress_tick = mock.Mock()

        app._set_ai_stage_ui("Inference", 20.0, 80.0, 12.0)

        self.assertEqual(app.ai_progress_stage, "Inference")
        self.assertAlmostEqual(app.ai_progress_stage_start, 30.0)
        self.assertAlmostEqual(app.ai_progress_stage_end, 45.0)
        self.assertEqual(app.ai_progress_stage_expected, 12.0)

        with mock.patch.object(APP, "_save_ai_duration_estimates"):
            app._record_ai_inference_duration("birefnet-massive", 10.0)
        self.assertAlmostEqual(app.ai_duration_estimates["birefnet-massive"], 23.6)

    def test_shutdown_signals_workers_and_releases_owned_ai_sessions(self):
        app = object.__new__(APP.TransparentorApp)
        app._shutdown_event = threading.Event()
        app._worker_threads = set()
        app._worker_threads_lock = threading.Lock()
        app._cleanup_complete = False
        app.ai_session_lock = threading.Lock()
        session = type("Session", (), {"inner_session": object()})()
        app.ai_sessions = {"birefnet-massive": session}
        app.batch_running = True
        app.original_img = Image.new("RGBA", (1, 1))
        app.edited_img = Image.new("RGBA", (1, 1))
        app.gif_src_images = [Image.new("RGBA", (1, 1))]
        app.gif_aligned_rgba = [Image.new("RGBA", (1, 1))]
        app.gif_thumb_refs = [object()]
        app.slicer_batch_images = [Image.new("RGBA", (1, 1))]
        app.slicer_boxes = [(0, 0, 1, 1)]
        app.composition_layers = [{"image": Image.new("RGBA", (1, 1))}]
        app.composition_history = [{}]
        app.composition_future_history = [{}]
        app.batch_preview_image = Image.new("RGBA", (1, 1))
        app.batch_filmstrip_refs = [object()]
        app.batch_thumbnail_cache = {"item": object()}

        app._cleanup_before_exit()

        self.assertTrue(app._shutdown_event.is_set())
        self.assertFalse(app.batch_running)
        self.assertEqual(app.ai_sessions, {})
        self.assertIsNone(session.inner_session)
        self.assertIsNone(app.original_img)
        self.assertEqual(app.composition_layers, [])

        source = (ROOT / "Transparentor.pyw").read_text(encoding="utf-8")
        self.assertNotIn("subprocess.Popen", source)
        self.assertNotIn("subprocess.run", source)

    def test_composition_renderer_respects_layer_order_position_and_scale(self):
        app = object.__new__(APP.TransparentorApp)
        app.composition_canvas_size = (4, 3)
        app.composition_layers = [
            {
                "name": "Background",
                "path": None,
                "image": Image.new("RGBA", (4, 3), (255, 0, 0, 255)),
                "x": 0,
                "y": 0,
                "scale": 1.0,
                "visible": True,
            },
            {
                "name": "Top",
                "path": None,
                "image": Image.new("RGBA", (1, 1), (0, 0, 255, 255)),
                "x": 1,
                "y": 1,
                "scale": 2.0,
                "visible": True,
            },
        ]

        result = app._render_composition_image()

        self.assertEqual(result.size, (4, 3))
        self.assertEqual(result.getpixel((0, 0)), (255, 0, 0, 255))
        self.assertEqual(result.getpixel((1, 1)), (0, 0, 255, 255))
        self.assertEqual(result.getpixel((2, 2)), (0, 0, 255, 255))

    def test_composition_renderer_applies_opacity_shadow_and_rotation_bounds(self):
        app = object.__new__(APP.TransparentorApp)
        app.composition_canvas_size = (4, 4)
        app.composition_preview_cache = {}
        app.composition_layers = [{
            "name": "Styled",
            "path": None,
            "image": Image.new("RGBA", (2, 1), (255, 0, 0, 255)),
            "x": 0,
            "y": 0,
            "scale": 1.0,
            "visible": True,
            "rotation": 90.0,
            "opacity": 0.5,
            "shadow_enabled": True,
            "shadow_opacity": 1.0,
            "shadow_blur": 0.0,
            "shadow_x": 2.0,
            "shadow_y": 1.0,
        }]

        result = app._render_composition_image()
        bounds = app._composition_layer_bounds(app.composition_layers[0])

        self.assertEqual(result.size, (4, 4))
        self.assertAlmostEqual(bounds[2] - bounds[0], 1.0, places=4)
        self.assertAlmostEqual(bounds[3] - bounds[1], 2.0, places=4)
        pixels = [
            result.getpixel((x, y))
            for y in range(result.height)
            for x in range(result.width)
        ]
        self.assertTrue(any(pixel[3] == 128 for pixel in pixels))
        self.assertTrue(any(pixel[:3] == (0, 0, 0) and pixel[3] > 0 for pixel in pixels))

    def test_composition_drag_uses_lightweight_preview_until_release(self):
        app = object.__new__(APP.TransparentorApp)
        app.composition_canvas_size = (1000, 800)
        app.composition_layers = [{
            "name": "Movable",
            "path": None,
            "image": Image.new("RGBA", (400, 300), (255, 255, 255, 255)),
            "x": 100.0,
            "y": 120.0,
            "scale": 1.0,
            "visible": True,
        }]
        app.composition_selected_index = 0
        app.composition_drag_state = {
            "type": "move",
            "offset_x": 20.0,
            "offset_y": 30.0,
        }
        app.composition_drag_history_pushed = False
        app.composition_history = []
        app.composition_future_history = []
        app.project_dirty = False
        app.canvas_to_image = lambda _x, _y: (350.0, 270.0)
        app._request_composition_preview = mock.Mock()
        app._update_composition_output = mock.Mock()
        event = type("Event", (), {"x": 1, "y": 1})()

        app._composition_drag_pointer(event)

        self.assertEqual(app.composition_layers[0]["x"], 330.0)
        self.assertEqual(app.composition_layers[0]["y"], 240.0)
        app._request_composition_preview.assert_called_once()
        app._update_composition_output.assert_not_called()

    def test_multi_file_drop_in_edit_routes_to_ai_queue_not_compose(self):
        app = object.__new__(APP.TransparentorApp)
        app.root = type(
            "Root",
            (),
            {"tk": type("Tk", (), {"splitlist": lambda _self, data: data})()},
        )()
        app.is_slicer_active = False
        app.is_composition_active = False
        app.png_gif_mode = Value(False)
        app._start_edit_image_queue = mock.Mock()
        app.enter_composition_mode = mock.Mock()
        app.composition_add_paths = mock.Mock()
        app._load_multiple_slicer_images = mock.Mock()
        app._load_multiple_gif_images = mock.Mock()

        with tempfile.TemporaryDirectory() as temp_dir:
            paths = [str(Path(temp_dir) / "one.png"), str(Path(temp_dir) / "two.webp")]
            for path in paths:
                Path(path).touch()
            event = type("DropEvent", (), {"data": paths})()

            app.on_drop(event)

        app._start_edit_image_queue.assert_called_once_with(paths)
        app.enter_composition_mode.assert_not_called()
        app.composition_add_paths.assert_not_called()

    def test_edit_queue_processes_the_next_queued_image_sequentially(self):
        app = object.__new__(APP.TransparentorApp)
        app.edit_queue_active = True
        app.edit_queue_running = True
        app.batch_files_list = ["first.png", "second.png", "third.png"]
        app.batch_item_statuses = ["done", "queued", "queued"]
        app.original_img = Image.new("RGBA", (2, 2), (12, 34, 56, 255))
        app._is_shutting_down = mock.Mock(return_value=False)
        app.open_image_from_path = mock.Mock(return_value=True)
        app._set_batch_preview_ui = mock.Mock()
        app._set_edit_queue_button = mock.Mock()
        app._run_ai_remove_current = mock.Mock()

        app._process_next_edit_queue_item()

        app.open_image_from_path.assert_called_once_with(
            "second.png",
            confirm_replace=False,
            preserve_edit_queue=True,
        )
        app._set_batch_preview_ui.assert_called_once_with(
            1,
            app.original_img,
            "processing",
            "Removing background • 2 of 3 • second.png",
        )
        app._run_ai_remove_current.assert_called_once()

    def test_u2net_home_is_used_as_the_model_directory(self):
        with mock.patch.dict(APP.os.environ, {"U2NET_HOME": str(ROOT / "model-cache")}):
            expected = ROOT / "model-cache" / "birefnet-massive.onnx"
            self.assertEqual(APP._model_cache_path("birefnet-massive"), expected)

    def test_lossless_webp_export_preserves_alpha(self):
        if not features.check("webp"):
            self.skipTest("This Pillow build does not provide WebP support.")
        image = Image.new("RGBA", (2, 1))
        image.putdata([(12, 34, 56, 255), (78, 90, 123, 17)])
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "transparent.webp"
            APP._save_transparent_image(image, output_path, "WEBP")
            with Image.open(output_path) as restored:
                self.assertEqual(restored.format, "WEBP")
                restored = restored.convert("RGBA")
                self.assertEqual(restored.getpixel((0, 0)), (12, 34, 56, 255))
                self.assertEqual(restored.getpixel((1, 0))[3], 17)

    def test_ico_export_contains_compatible_multiresolution_frames(self):
        import struct

        source = Image.new("RGBA", (901, 701), (0, 0, 0, 0))
        source.paste((40, 150, 255, 255), (80, 40, 820, 660))
        app = object.__new__(APP.TransparentorApp)
        app.edited_img = source

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "multisize.ico"
            app._save_as_ico(str(output_path))
            icon_bytes = output_path.read_bytes()
            reserved, image_type, count = struct.unpack_from(
                "<HHH",
                icon_bytes,
                0,
            )
            sizes = []
            signatures = []
            for index in range(count):
                (
                    width,
                    height,
                    _colors,
                    _entry_reserved,
                    _planes,
                    bits_per_pixel,
                    byte_count,
                    image_offset,
                ) = struct.unpack_from(
                    "<BBBBHHII",
                    icon_bytes,
                    6 + index * 16,
                )
                sizes.append(
                    (
                        256 if width == 0 else width,
                        256 if height == 0 else height,
                    )
                )
                signatures.append(
                    icon_bytes[image_offset:image_offset + 4]
                )
                self.assertEqual(bits_per_pixel, 32)
                self.assertGreater(byte_count, 40)

            self.assertEqual((reserved, image_type), (0, 1))
            self.assertEqual(
                sizes,
                [
                    (256, 256),
                    (128, 128),
                    (64, 64),
                    (48, 48),
                    (32, 32),
                    (24, 24),
                    (16, 16),
                ],
            )
            self.assertTrue(
                all(signature == b"\x28\x00\x00\x00" for signature in signatures)
            )
            with Image.open(output_path) as loaded:
                self.assertEqual(loaded.size, (256, 256))
                self.assertEqual(
                    loaded.ico.sizes(),
                    {
                        (16, 16),
                        (24, 24),
                        (32, 32),
                        (48, 48),
                        (64, 64),
                        (128, 128),
                        (256, 256),
                    },
                )

    def test_edit_stack_applies_crop_then_exact_resize(self):
        app = object.__new__(APP.TransparentorApp)
        source = Image.new("RGBA", (8, 6), (0, 0, 0, 0))
        for y in range(source.height):
            for x in range(source.width):
                source.putpixel((x, y), (x * 20, y * 30, 100, 255))
        app.original_img = source
        app.edited_img = source.copy()
        app.actions = [
            {
                "type": "crop",
                "box": (2, 1, 7, 5),
                "desc": "Crop 5 × 4 px at 2, 1",
            },
            {
                "type": "resize",
                "width": 10,
                "height": 8,
                "resample": "nearest",
                "desc": "Resize to 10 × 8 px",
            },
        ]
        app.history = [source.copy()]
        app._last_applied_action_count = 0
        app.protected_mask = set()
        app.project_dirty = False

        app.apply_actions()

        self.assertEqual(app.edited_img.size, (10, 8))
        self.assertEqual(app.edited_img.getpixel((0, 0)), source.getpixel((2, 1)))
        self.assertEqual(app.edited_img.getpixel((9, 7)), source.getpixel((6, 4)))
        self.assertEqual(len(app.history), 3)
        self.assertTrue(app.project_dirty)

    def test_ai_action_images_round_trip_through_project_archive(self):
        mask = Image.new("L", (3, 2), 127)
        action = {
            "type": "ai_remove",
            "box": (1, 2, 3, 4),
            "points": [(1, 1), (2, 2)],
            "ai_mask": mask,
            "composite_mask": mask.copy(),
            "refinement_mask": None,
            "desc": "AI removal",
        }

        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            serialized = APP._serialize_project_action(action, 0, archive)
            archive.writestr("action.json", json.dumps(serialized))

        buffer.seek(0)
        with zipfile.ZipFile(buffer, "r") as archive:
            serialized = json.loads(archive.read("action.json"))
            restored = APP._deserialize_project_action(serialized, archive)

        self.assertEqual(restored["box"], (1, 2, 3, 4))
        self.assertEqual(restored["points"], [(1, 1), (2, 2)])
        self.assertEqual(restored["ai_mask"].mode, "L")
        self.assertEqual(restored["ai_mask"].getpixel((0, 0)), 127)

    def test_save_project_embeds_editor_slicer_gif_and_protection(self):
        app = object.__new__(APP.TransparentorApp)
        app.original_img = Image.new("RGBA", (4, 4), (20, 40, 60, 255))
        app.edited_img = app.original_img.copy()
        app.editor_image_path = None
        app.actions = [{
            "type": "ai_remove",
            "desc": "AI removal",
            "ai_mask": Image.new("L", (4, 4), 255),
        }]
        app.protected_mask = {(1, 1), (2, 2)}
        app.slicer_image = Image.new("RGBA", (2, 2), (255, 0, 0, 255))
        app.slicer_image_path = None
        app.gif_src_images = [Image.new("RGBA", (2, 2), (0, 255, 0, 255))]
        app.gif_frame_paths = ["slice_001.png"]
        app.gif_frame_omitted = [False]
        app.gif_template_box = None
        app.gif_template_frame_idx = None
        app.current_project_path = None
        app.project_dirty = True
        app.is_composition_active = True
        app.composition_canvas_size = (4, 4)
        app.composition_selected_index = 0
        app.composition_layers = [{
            "name": "Overlay",
            "path": None,
            "image": Image.new("RGBA", (2, 2), (0, 0, 255, 128)),
            "x": 1.0,
            "y": 1.0,
            "scale": 1.5,
            "visible": True,
            "rotation": 22.0,
            "opacity": 0.7,
            "brightness": 1.15,
            "contrast": 0.9,
            "saturation": 1.25,
            "blur": 1.5,
            "shadow_enabled": True,
            "shadow_opacity": 0.4,
            "shadow_blur": 12.0,
            "shadow_x": 8.0,
            "shadow_y": 10.0,
            "flip_x": True,
            "flip_y": False,
        }]

        app.slicer_cols = Value(1)
        app.slicer_rows = Value(1)
        app.slicer_margin_x = Value(0)
        app.slicer_margin_y = Value(0)
        app.slicer_padding_x = Value(0)
        app.slicer_padding_y = Value(0)
        app.slicer_expand_w = Value(0)
        app.slicer_expand_h = Value(0)
        app.slicer_crop_center_content = Value(True)
        app.slicer_crop_square = Value(False)
        app.slicer_use_manual = Value(False)
        app.slicer_trim_transparency = Value(False)
        app.slicer_trim_threshold = Value(10)
        app.slicer_export_format = Value("WEBP")
        app.slicer_boxes = []
        app.gif_anchor = Value("center")
        app.gif_duration_ms = Value(80)
        app.gif_alpha_threshold = Value(1)
        app.gif_padding = Value(0)
        app.gif_frame_export_format = Value("WEBP")

        with tempfile.TemporaryDirectory() as temp_dir:
            project_path = Path(temp_dir) / "portable.tpr"
            with (
                mock.patch.object(APP.filedialog, "asksaveasfilename", return_value=str(project_path)),
                mock.patch.object(APP.messagebox, "showinfo"),
                mock.patch.object(APP.messagebox, "showerror"),
            ):
                self.assertTrue(app.save_project())

            self.assertTrue(zipfile.is_zipfile(project_path))
            with zipfile.ZipFile(project_path, "r") as archive:
                names = set(archive.namelist())
                manifest = json.loads(archive.read("project.json"))

            self.assertEqual(manifest["format_version"], 4)
            self.assertIn("assets/editor/source.png", names)
            self.assertIn("assets/editor/protected_mask.png", names)
            self.assertIn("assets/actions/0000_ai_mask.png", names)
            self.assertIn("assets/slicer/source.png", names)
            self.assertIn("assets/gif/frame_0000.png", names)
            self.assertIn("assets/composition/layer_0000.png", names)
            self.assertEqual(manifest["slicer"]["settings"]["export_format"], "WEBP")
            self.assertEqual(manifest["gif"]["frame_export_format"], "WEBP")
            self.assertTrue(manifest["composition"]["active"])
            self.assertEqual(manifest["composition"]["layers"][0]["scale"], 1.5)
            self.assertEqual(manifest["composition"]["layers"][0]["rotation"], 22.0)
            self.assertEqual(manifest["composition"]["layers"][0]["opacity"], 0.7)
            self.assertTrue(manifest["composition"]["layers"][0]["shadow_enabled"])
            self.assertFalse(app.project_dirty)

    def test_ui_project_save_and_load_round_trip(self):
        original_preload = APP.TransparentorApp._pre_initialize_ai
        APP.TransparentorApp._pre_initialize_ai = lambda _self: None
        try:
            root = APP.TkinterDnD.Tk()
        except Exception as error:
            APP.TransparentorApp._pre_initialize_ai = original_preload
            self.skipTest(f"Tk is unavailable in this environment: {error}")

        try:
            root.withdraw()
            app = APP.TransparentorApp(root)
            source = Image.new("RGBA", (6, 5), (30, 60, 90, 255))
            app.open_image_from_pil(source, confirm_replace=False)
            app.actions = [
                {
                    "type": "crop",
                    "box": (1, 1, 5, 4),
                    "desc": "Crop round-trip",
                },
                {
                    "type": "resize",
                    "width": 8,
                    "height": 6,
                    "resample": "lanczos",
                    "desc": "Resize round-trip",
                },
            ]
            app.protected_mask = {(2, 2)}
            app.slicer_image = Image.new("RGBA", (3, 2), (200, 50, 25, 255))
            app.slicer_image_path = None
            app.gif_frame_paths = ["generated_frame.png"]
            app.gif_src_images = [Image.new("RGBA", (2, 2), (25, 200, 50, 255))]
            app.gif_frame_omitted = [True]
            app.enter_composition_mode()
            app.composition_add_pil_image(
                Image.new("RGBA", (2, 2), (20, 40, 255, 180)),
                name="roundtrip-overlay.webp",
            )
            app.composition_layers[-1].update({
                "rotation": 33.0,
                "opacity": 0.65,
                "brightness": 1.1,
                "shadow_enabled": True,
                "shadow_opacity": 0.35,
                "shadow_blur": 9.0,
                "shadow_x": 5.0,
                "shadow_y": 7.0,
            })
            app.project_dirty = True

            with tempfile.TemporaryDirectory() as temp_dir:
                project_path = Path(temp_dir) / "roundtrip.tpr"
                with (
                    mock.patch.object(APP.filedialog, "asksaveasfilename", return_value=str(project_path)),
                    mock.patch.object(APP.messagebox, "showinfo"),
                    mock.patch.object(APP.messagebox, "showerror"),
                ):
                    self.assertTrue(app.save_project())

                app.original_img = None
                app.edited_img = None
                app.slicer_image = None
                app.gif_src_images = []
                app.gif_frame_paths = []
                app.actions = []
                app._clear_composition_state()

                with (
                    mock.patch.object(APP.filedialog, "askopenfilename", return_value=str(project_path)),
                    mock.patch.object(APP.messagebox, "showinfo"),
                    mock.patch.object(APP.messagebox, "showerror"),
                ):
                    self.assertTrue(app.load_project())

                self.assertEqual(app.original_img.size, (6, 5))
                # The restored composition owns the preview at this point;
                # verify the editor resize action itself was retained below.
                self.assertEqual(app.edited_img.size, (6, 5))
                self.assertEqual(app.actions[-1]["type"], "resize")
                self.assertEqual(app.actions[-1]["resample"], "lanczos")
                self.assertEqual(len(app.composition_layers), 2)
                self.assertEqual(app.composition_layers[-1]["name"], "roundtrip-overlay.webp")
                self.assertEqual(app.composition_layers[-1]["rotation"], 33.0)
                self.assertEqual(app.composition_layers[-1]["opacity"], 0.65)
                self.assertTrue(app.composition_layers[-1]["shadow_enabled"])
                self.assertTrue(app.is_composition_active)
                self.assertIn((2, 2), app.protected_mask)
                self.assertEqual(app.slicer_image.size, (3, 2))
                self.assertEqual(len(app.gif_src_images), 1)
                self.assertEqual(app.gif_frame_omitted, [True])
                self.assertFalse(app.project_dirty)
        finally:
            APP.TransparentorApp._pre_initialize_ai = original_preload
            try:
                root.destroy()
            except Exception:
                pass


if __name__ == "__main__":
    unittest.main()
