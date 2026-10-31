"""Shared serving state for both HTTP adapters."""
import json
from pathlib import Path
import threading
import time
import uuid
import release

class Unavailable(Exception): pass

class StubBackend:
    label = 'STUB ONLY'
    def __init__(self, manifest):
        self.loaded_id = manifest['model_id']
        self.runtime_sha256 = manifest['runtime_sha256']
        self.calls = 0
    def generate(self, prompt, limit):
        self.calls += 1
        time.sleep(.01)
        return {'answer':f'STUB ONLY: {self.loaded_id}', 'output_tokens':1}
    def warmup(self): pass

class TransformersBackend:
    label = 'Transformers (real weights)'
    def __init__(self, manifest):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
        self.torch = torch
        self.loaded_id = manifest['model_id']
        self.runtime_sha256 = manifest['runtime_sha256']
        self.calls = 0
        self.runtime = manifest['runtime']
        from importlib.metadata import version
        for library, expected in self.runtime['libraries'].items():
            if version(library).split('+')[0] != expected:
                raise ValueError(f'Generator library differs from evaluated runtime: {library}')
        torch.set_num_threads(4)
        torch.manual_seed(self.runtime['generation'].get('seed', 42))
        root = manifest.get('base_root',manifest['artifact_root'])
        self.tokenizer = AutoTokenizer.from_pretrained(manifest.get('tokenizer_root',root), local_files_only=True)
        if release.digest(self.tokenizer.chat_template.encode()) != self.runtime['template_sha256']:
            raise ValueError('Chat template changed')
        self.model = AutoModelForCausalLM.from_pretrained(root, local_files_only=True, dtype=getattr(torch, self.runtime['dtype'])).to(self.runtime['device']).eval()
        if manifest.get('adapter_root'):
            from peft import PeftModel
            self.model = PeftModel.from_pretrained(self.model, manifest['adapter_root'], local_files_only=True).eval()
    def generate(self, prompt, limit):
        config = self.runtime['generation']
        text = self.tokenizer.apply_chat_template([{'role':'system','content':config['system']}, {'role':'user','content':prompt}], tokenize=False, add_generation_prompt=True, enable_thinking=config['enable_thinking'])
        batch = self.tokenizer(text, return_tensors='pt').to(self.runtime['device'])
        if batch['input_ids'].shape[1] > self.runtime['max_input_tokens']:
            raise ValueError('Tokenized input too long')
        self.calls += 1
        with self.torch.inference_mode():
            output = self.model.generate(**batch, max_new_tokens=limit, do_sample=config['do_sample'], pad_token_id=self.tokenizer.pad_token_id or self.tokenizer.eos_token_id)
        tokens = output[0, batch['input_ids'].shape[1]:]
        return {'answer':self.tokenizer.decode(tokens, skip_special_tokens=True), 'output_tokens':len(tokens)}
    def warmup(self): self.generate('Что выведет print(1+1)? A: 2; B: 3.', self.runtime['generation']['max_new_tokens'])

class ServiceState:
    def __init__(self, root, warmup_seconds=0, backend_factory=StubBackend):
        self.root = Path(root)
        self.backend = None
        self.error = None
        self.lock = threading.Lock()
        self.warmup_finished = threading.Event()
        self.manifest = json.loads((self.root/'accepted.json').read_text())
        def load():
            try:
                m = self.manifest
                if release.digest(release.canonical(m['runtime'])) != m['runtime_sha256']:
                    raise ValueError('Runtime hash mismatch')
                release.verify_files(m, self.root)
                self.backend = backend_factory(m)
                self.backend.warmup()
                time.sleep(warmup_seconds)
                self.warmup_finished.set()
            except Exception as exc: self.error = f'{type(exc).__name__}: {exc}'
        self.thread = threading.Thread(target=load, daemon=True)
        self.thread.start()
    @property
    def ready(self): return self.warmup_finished.is_set() and self.error is None
    def debug(self):
        return {'loaded_id':self.backend.loaded_id if self.backend else None, 'calls':self.backend.calls if self.backend else 0, 'warmup_finished':self.warmup_finished.is_set(), 'error':self.error}
    def generate(self, request):
        started = time.perf_counter()
        if not self.ready: raise Unavailable('Model is not ready')
        if not isinstance(request, dict): raise ValueError('Expected JSON object')
        prompt = request.get('prompt')
        limit = request.get('max_new_tokens', self.manifest['runtime']['generation']['max_new_tokens'])
        if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 8192:
            raise ValueError('prompt must contain 1..8192 characters')
        if type(limit) is not int or limit != self.manifest['runtime']['generation']['max_new_tokens']:
            raise ValueError('max_new_tokens must equal the evaluated budget')
        if set(request) - {'prompt','max_new_tokens'}: raise ValueError('Unknown request fields')
        with self.lock:
            compute_start = time.perf_counter()
            result = self.backend.generate(prompt, limit)
            duration = time.perf_counter()-compute_start
        result.update(model_id=self.backend.loaded_id, runtime_sha256=self.backend.runtime_sha256,
                      request_id=str(uuid.uuid4()), generation_seconds=duration,
                      queue_seconds=compute_start-started, total_seconds=time.perf_counter()-started)
        return result
