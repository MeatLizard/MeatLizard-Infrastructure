# client_bot/llama_cpp_wrapper.py
import subprocess
import threading
import queue
import platform
import os
from pydantic import BaseModel, Field
from typing import Optional

# --- Configuration Models ---
class LlamaCppConfig(BaseModel):
    """Configuration for the llama.cpp executable."""
    # Path to the main llama.cpp executable
    executable_path: str = "./llama.cpp/main"
    # Default model to use if not specified in the request
    default_model_path: str
    # Number of threads to use for inference
    threads: int = 8
    # GPU layers to offload. A high number is good for performance.
    n_gpu_layers: int = 35 # Default for Llama 2 7B on M1/M2
    # Context size
    n_ctx: int = 4096
    # Additional flags to pass to the executable
    extra_flags: list[str] = []

class InferenceRequest(BaseModel):
    """Represents a single request for LLM inference."""
    prompt: str
    model_path: Optional[str] = None # If None, use the default from config
    temperature: float = 0.8
    top_p: float = 0.95
    max_tokens: int = 2048

class InferenceResult(BaseModel):
    """The result of an LLM inference."""
    text: str
    tokens_per_second: float = 0.0
    inference_time_ms: int = 0

class LlamaCppWrapper:
    """
    A wrapper for running inference with the llama.cpp executable.

    This class manages the subprocess, handles input/output, and is designed
    to be run in a separate thread to avoid blocking the Discord bot's event loop.
    """
    def __init__(self, config: LlamaCppConfig):
        self.config = config
        self._validate_config()
        self.process = None
        self.input_queue = queue.Queue()
        self.output_queue = queue.Queue()
        self.thread = threading.Thread(target=self._run_inference_loop, daemon=True)

    def _validate_config(self):
        """Ensures that the executable and model paths are valid."""
        if not os.path.exists(self.config.executable_path):
            raise FileNotFoundError(
                f"llama.cpp executable not found at: {self.config.executable_path}"
            )
        if not os.path.exists(self.config.default_model_path):
            raise FileNotFoundError(
                f"Default model not found at: {self.config.default_model_path}"
            )
        if platform.system() != "Darwin":
            print("Warning: This wrapper is optimized for macOS with Metal (MPS).")

    def start(self):
        """Starts the inference loop thread."""
        self.thread.start()

    def stop(self):
        """Stops the inference loop."""
        self.input_queue.put(None) # Sentinel value to stop the loop
        if self.process:
            self.process.terminate()
        self.thread.join()

    def submit_request(self, request: InferenceRequest) -> "queue.Queue":
        """Submits a request to the inference queue and returns a queue for the result."""
        result_queue = queue.Queue()
        self.input_queue.put((request, result_queue))
        return result_queue

    def _run_inference_loop(self):
        """
        The main loop that waits for requests and runs the llama.cpp process.
        This runs in a separate thread.
        """
        while True:
            item = self.input_queue.get()
            if item is None:
                break # Stop the loop

            request, result_queue = item
            
            try:
                command = self._build_command(request)
                print(f"Running command: {' '.join(command)}")

                # --- Subprocess Execution ---
                # This is a simplified example. A production version would need
                # more robust error handling, stream parsing for metrics, etc.
                process = subprocess.Popen(
                    command,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding='utf-8'
                )

                # Write the prompt to stdin
                process.stdin.write(request.prompt)
                process.stdin.close()

                # Read the output
                stdout, stderr = process.communicate()

                if process.returncode != 0:
                    raise RuntimeError(f"llama.cpp process failed:\n{stderr}")

                # --- Result Parsing (Simplified) ---
                # A real implementation would parse the stderr stream for metrics
                # like tokens/sec that llama.cpp prints during generation.
                result = InferenceResult(
                    text=stdout.strip(),
                    # Dummy metrics for now
                    tokens_per_second=50.0,
                    inference_time_ms=1500
                )
                result_queue.put(result)

            except Exception as e:
                print(f"Error during inference: {e}")
                result_queue.put(e)


    def _build_command(self, request: InferenceRequest) -> list[str]:
        """Constructs the command-line arguments for llama.cpp."""
        model_path = request.model_path or self.config.default_model_path
        
        command = [
            self.config.executable_path,
            "-m", model_path,
            "-t", str(self.config.threads),
            "-c", str(self.config.n_ctx),
            "-n", str(request.max_tokens),
            "--temp", str(request.temperature),
            "--top-p", str(request.top_p),
            "--no-display-prompt", # Don't print the prompt in the output
        ]

        # Add Metal (MPS) flags if on macOS
        if platform.system() == "Darwin":
            command.extend([
                "-ngl", str(self.config.n_gpu_layers),
            ])

        command.extend(self.config.extra_flags)
        return command


# --- Example Usage ---
if __name__ == "__main__":
    # This demonstrates how the wrapper would be used by the client-bot.
    # NOTE: You must have the llama.cpp executable and a model file at the specified paths.
    
    # Create a dummy executable and model for testing if they don't exist
    if not os.path.exists("./llama.cpp"):
        os.makedirs("./llama.cpp")
    if not os.path.exists("./llama.cpp/main"):
        with open("./llama.cpp/main", "w") as f:
            f.write("#!/bin/bash\necho 'Hello from dummy llama.cpp!'")
        os.chmod("./llama.cpp/main", 0o755)
    if not os.path.exists("./models"):
        os.makedirs("./models")
    if not os.path.exists("./models/dummy_model.gguf"):
        with open("./models/dummy_model.gguf", "w") as f:
            f.write("dummy model data")

    config = LlamaCppConfig(
        executable_path="./llama.cpp/main",
        default_model_path="./models/dummy_model.gguf",
        n_gpu_layers=35
    )

    wrapper = LlamaCppWrapper(config)
    wrapper.start()

    print("Submitting inference request...")
    request = InferenceRequest(prompt="What is the capital of France?")
    
    result_queue = wrapper.submit_request(request)
    
    try:
        # Wait for the result
        result = result_queue.get(timeout=10)
        if isinstance(result, Exception):
            print(f"Inference failed: {result}")
        else:
            print(f"Inference successful!")
            print(f"Response: {result.text}")
            print(f"Metrics: {result.tokens_per_second} t/s")

    except queue.Empty:
        print("Inference request timed out.")

    finally:
        print("Stopping wrapper.")
        wrapper.stop()