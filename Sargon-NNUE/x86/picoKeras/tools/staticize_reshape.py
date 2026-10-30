"""Staticize TFLite dynamic shapes for batch=1 TFLM inference.

Requires TensorFlow (the same environment used for conversion), flatbuffers.
No model is published unless reference and patched inference match exactly.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np


def load_schema():
    import flatbuffers
    from tensorflow.lite.python import schema_py_generated as schema
    return flatbuffers, schema


def interpreter(tf, data):
    return tf.lite.Interpreter(model_content=data, experimental_preserve_all_tensors=True, num_threads=1)


def probe(tf, blob, samples):
    it = interpreter(tf, blob)
    ins = it.get_input_details()
    if len(ins) != 1:
        raise RuntimeError(f'Expected one input, got {len(ins)}')
    ii = ins[0]
    if tuple(ii['shape']) != (1,8,8,12) or ii['dtype'] != np.int8:
        raise RuntimeError(f'Input unsupported: {ii["shape"]}, {ii["dtype"]}')
    it.allocate_tensors()
    all_shapes = None
    outputs = []
    for sample in samples:
        it.set_tensor(ii['index'], sample)
        it.invoke()
        now = {int(t['index']): [int(x) for x in t['shape']] for t in it.get_tensor_details()}
        if all_shapes is not None and now != all_shapes:
            changed = [i for i in now if now[i]!=all_shapes.get(i)]
            raise RuntimeError(f'Dynamic shapes depend on input; cannot freeze: {changed[:12]}')
        all_shapes = now
        outputs.append([it.get_tensor(o['index']).copy() for o in it.get_output_details()])
    return all_shapes,outputs


def rewrite(source, runtime_shapes, schema, flatbuffers):
    model = schema.Model.GetRootAsModel(source,0)
    decoded = schema.ModelT.InitFromObj(model)
    if len(decoded.subgraphs)!=1: raise RuntimeError('Multiple subgraphs not supported')
    graph=decoded.subgraphs[0]
    replaced=[]
    for op_index,op in enumerate(graph.operators):
        opcode=decoded.operatorCodes[op.opcodeIndex]
        builtin=int(opcode.builtinCode)
        if builtin != int(schema.BuiltinOperator.RESHAPE): continue
        if len(op.outputs)!=1 or len(op.inputs)<1: raise RuntimeError(f'Invalid RESHAPE {op_index}')
        inp_idx=int(op.inputs[0]); out_idx=int(op.outputs[0]);
        old=graph.tensors[inp_idx]; new=graph.tensors[out_idx]
        srcshape=runtime_shapes.get(inp_idx); destshape=runtime_shapes.get(out_idx)
        if not srcshape or not destshape: raise RuntimeError(f'Unknown shape RESHAPE {op_index}')
        def n(shape): return int(np.prod(shape,dtype=np.int64))
        if n(srcshape)!=n(destshape):
            raise RuntimeError(f'RESHAPE op {op_index} violates element count: {srcshape} -> {destshape}')
        if len(op.inputs)>1:
            op.inputs=[inp_idx] # TFLM must use static ReshapeOptions, not dynamic shape input.
        if op.builtinOptions is None or not isinstance(op.builtinOptions,schema.ReshapeOptionsT):
            op.builtinOptions=schema.ReshapeOptionsT()
            op.builtinOptionsType=schema.BuiltinOptions.ReshapeOptions
        op.builtinOptions.newShape=destshape
        replaced.append({'op':op_index,'input':srcshape,'output':destshape})
    if not replaced: raise RuntimeError('No RESHAPE operations found')
    frozen=0
    for idx,shape in runtime_shapes.items():
        if idx<0 or idx>=len(graph.tensors): continue
        tensor=graph.tensors[idx]
        # FlatBuffers generated *T objects often store shape as numpy.ndarray.
        # ndarray != list returns a boolean array, not a scalar boolean.
        current_shape = tuple(int(d) for d in tensor.shape) if tensor.shape is not None else ()
        target_shape = tuple(int(d) for d in shape)
        if current_shape != target_shape:
            tensor.shape = list(target_shape)
            frozen += 1
        # batch=1 fixed; dynamic shapeSignature no longer applies
        tensor.shapeSignature=[]
    builder=flatbuffers.Builder(1024)
    builder.Finish(decoded.Pack(builder),file_identifier=b'TFL3')
    return bytes(builder.Output()),replaced,frozen


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--input',required=True)
    p.add_argument('--output',required=True)
    p.add_argument('--report',required=True)
    p.add_argument('--samples',type=int,default=4)
    a=p.parse_args()
    if a.samples<2: p.error('samples >=2 required')
    import tensorflow as tf
    fb,schema=load_schema()
    src=Path(a.input).read_bytes()
    rng=np.random.default_rng(411)
    samples=[rng.integers(-128,128,size=(1,8,8,12),dtype=np.int16).astype(np.int8) for _ in range(a.samples)]
    samples[0].fill(0)
    report={'status':'FAIL','source_sha256':hashlib.sha256(src).hexdigest(),'samples':a.samples}
    out=Path(a.output); rep=Path(a.report)
    try:
        shapes,expected=probe(tf,src,samples)
        patched,ops,frozen=rewrite(src,shapes,schema,fb)
        _,actual=probe(tf,patched,samples)
        diffs=[]
        for one,two in zip(expected,actual):
            if len(one)!=len(two): raise RuntimeError('Output count changed')
            diffs += [int(np.max(np.abs(x.astype(np.int32)-y.astype(np.int32)))) for x,y in zip(one,two)]
        report.update(reshape_ops=len(ops),frozen_tensors=frozen,reshape_detail=ops,
                      max_output_int8_difference=max(diffs),patched_sha256=hashlib.sha256(patched).hexdigest())
        if max(diffs)!=0: raise RuntimeError('Output changed: refusing to publish')
        out.parent.mkdir(parents=True,exist_ok=True)
        out.write_bytes(patched)
        report['status']='PASS'
        report['output']=str(out.resolve())
        print(f'[picoKeras] PASS: frozen {len(ops)} RESHAPE operators; output difference=0; model={out}')
    except Exception as e:
        report['error']=f'{type(e).__name__}: {e}'
        print(f'[picoKeras] FAIL: {report["error"]}')
        raise
    finally:
        rep.parent.mkdir(parents=True,exist_ok=True)
        rep.write_text(json.dumps(report,indent=2),encoding='utf-8')

if __name__=='__main__':main()
