"""Pure-tensor regression tests; python-chess and EvoTorch are not needed here."""
import unittest
import numpy as np
import torch
from gen_grumpy_pgpe_core import (PARAMS, MATERIAL, factor_index, forward,
                                  to_torch, loss_parts, cp_objective, metrics)


class GrumpyContract(unittest.TestCase):
    def make_data(self):
        xs=np.zeros((3,2,64),dtype=np.int16)
        # two active rank/file features for 2 pieces; independent perspectives
        xs[:,0,:4]=np.array([[0,8,16,24],[1,9,17,25],[2,10,18,26]])
        xs[:,1,:4]=np.array([[48,56,64,72],[49,57,65,73],[50,58,66,74]])
        n=np.full(3,4,dtype=np.int64)
        b=np.zeros(3,dtype=np.int64)
        m=np.array([900,-900,0],dtype=np.float32)
        signs=np.array([1,-1,1],dtype=np.float32)
        y=np.array([1900,-1900,-500],dtype=np.float32)
        return to_torch((xs,n,b,m,signs,y))

    def test_grumpy_parameter_contract(self):
        self.assertEqual(PARAMS,1680)
        self.assertEqual(MATERIAL,(100,300,300,500,900,0))
        self.assertEqual(factor_index(0),(0,8))
        self.assertEqual(factor_index(63),(7,15))
        self.assertEqual(factor_index(64),(16,24))

    def test_fixed_material_and_stm_sign(self):
        data=self.make_data()
        w=torch.zeros(PARAMS)
        self.assertTrue(torch.allclose(forward(w,data),data[3]))
        # GRMP0001 bucket bias contributes 8*(400/1024)=3.125 cp
        w[1672]=1
        expected=data[3]+data[4]*3.125
        self.assertTrue(torch.allclose(forward(w,data),expected))

    def test_rank_and_gradient_preserve_magnitude(self):
        data=self.make_data()
        w=torch.zeros(PARAMS,requires_grad=True)
        with torch.no_grad():
            w[:1536].fill_(0.05)
            w[1536:1544].fill_(2)
            w[1544:1672].fill_(1)
        pred=forward(w,data)
        loss,prob,cp=loss_parts(pred,data[-1],1.0)
        self.assertTrue(float(cp)>0)
        self.assertTrue(float(prob)>0)
        loss.backward()
        self.assertTrue(torch.isfinite(w.grad).all())
        self.assertGreater(float(w.grad.abs().sum()),0)
        self.assertGreater(float(w.grad[1544:1680].abs().sum()),0)
        self.assertTrue(np.isfinite(metrics(pred.detach().numpy(),data[-1].numpy())['rmse_cp']))

    def test_evotorch_readonly_population_fitness(self):
        # Simulate the EvoTorch ReadOnlyTensor contract on CPU. The previous
        # implementation retained the subclass and crashed on `sum_loss +=`.
        # Load the exact function under test without unrelated CLI/IO imports.
        import ast
        from pathlib import Path
        source=Path(__file__).with_name('genGrumpyPGPE.py').read_text(encoding='utf-8')
        node=next(n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef) and n.name=='fitness_population')
        scope={'torch':torch,'forward':forward,'loss_parts':loss_parts,'cp_objective':cp_objective}
        exec(compile(ast.Module(body=[node],type_ignores=[]),'<fitness_population>','exec'),scope)
        fitness_population=scope['fitness_population']
        class ReadOnly(torch.Tensor):
            def __iadd__(self, other):
                raise TypeError('The contents of a ReadOnlyTensor cannot be modified')
        data=self.make_data()
        source=torch.zeros((4,PARAMS),dtype=torch.float32)
        source[:,1536:1544]=2.0
        values=source.as_subclass(ReadOnly)
        actual=fitness_population(values,data,torch.device('cpu'),2,2)
        expected=torch.stack([((forward(w,data)-data[-1])/2000.0).square().mean() for w in source])
        self.assertEqual(type(actual),torch.Tensor)
        self.assertTrue(torch.allclose(actual,expected,rtol=1e-6,atol=1e-6))

    def test_cpu_adam_keeps_state_on_host_and_updates(self):
        # Execute the same helper used by MON 7; CPU here verifies the
        # gradient transfer/update contract without requiring Intel XPU.
        import ast
        from pathlib import Path
        source=Path(__file__).with_name('genGrumpyPGPE.py').read_text(encoding='utf-8')
        node=next(n for n in ast.parse(source).body
                  if isinstance(n,ast.FunctionDef) and n.name=='refine_cpu_adam')
        scope={'torch':torch,'forward':forward,'loss_parts':loss_parts,'cp_objective':cp_objective}
        exec(compile(ast.Module(body=[node],type_ignores=[]),'<refine_cpu_adam>','exec'),scope)
        data=self.make_data()
        w=torch.nn.Parameter(torch.zeros(PARAMS,dtype=torch.float32))
        with torch.no_grad():
            w[:1536].fill_(0.05)
            w[1536:1544].fill_(2)
            w[1544:1672].fill_(1)
        before=w.detach().clone()
        optimizer=torch.optim.Adam([w],lr=0.03,foreach=False)
        scope['refine_cpu_adam'](w,optimizer,data,torch.device('cpu'),2)
        self.assertFalse(torch.equal(before,w.detach()))
        self.assertEqual(w.device.type,'cpu')
        self.assertGreater(len(optimizer.state[w]),0)
        self.assertTrue(all(not torch.is_tensor(x) or x.device.type=='cpu'
                            for x in optimizer.state[w].values()))

    def test_validation_chunking_and_cp_checkpoint_selection(self):
        import ast
        from pathlib import Path
        source=Path(__file__).with_name('genGrumpyPGPE.py').read_text(encoding='utf-8')
        names={'evaluate_validation','better_validation'}
        nodes=[n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef) and n.name in names]
        scope={'torch':torch,'np':np,'forward':forward}
        exec(compile(ast.Module(body=nodes,type_ignores=[]),'<validation>','exec'),scope)
        data=self.make_data()
        w=torch.zeros(PARAMS,dtype=torch.float32)
        pred=forward(w,data)
        expected=metrics(pred.numpy(),data[-1].numpy())
        observed=scope['evaluate_validation'](w,data,torch.device('cpu'),chunk=1)
        self.assertEqual(observed['positions'],3)
        for key in expected:
            self.assertAlmostEqual(expected[key],observed[key],places=5,msg=key)
        improve={'rmse_cp':700.0,'mse_probability':0.3}
        worsen={'rmse_cp':750.0,'mse_probability':0.01}
        self.assertTrue(scope['better_validation'](improve,None))
        self.assertFalse(scope['better_validation'](worsen,improve))
        self.assertTrue(scope['better_validation'](improve,worsen))

    def test_cp_only_fitness_not_sigmoid(self):
        import ast
        from pathlib import Path
        source=Path(__file__).with_name('genGrumpyPGPE.py').read_text(encoding='utf-8')
        node=next(n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef) and n.name=='fitness_population')
        scope={'torch':torch,'forward':forward,'cp_objective':cp_objective}
        exec(compile(ast.Module(body=[node],type_ignores=[]),'<fitness>','exec'),scope)
        data=self.make_data()
        w=torch.zeros((2,PARAMS),dtype=torch.float32)
        w[1,1672]=10.0
        got=scope['fitness_population'](w,data,torch.device('cpu'),2,1)
        true=torch.stack([cp_objective(forward(row,data),data[-1]) for row in w])
        self.assertTrue(torch.allclose(got,true,atol=1e-7))

    def test_batched_matches_individual_and_gradient(self):
        data=self.make_data()
        g=torch.Generator().manual_seed(99)
        weights=torch.randn((3,PARAMS),generator=g)*0.1
        batched=forward(weights,data)
        sequential=torch.stack([forward(row,data) for row in weights])
        self.assertTrue(torch.allclose(batched,sequential,atol=1e-5,rtol=1e-5))

# Resume contract test; no GPU or EvoTorch installation needed.
class GrumpyResumeContract(unittest.TestCase):
    def test_resume_keeps_legacy_checkpoint_identity_and_rejects_mismatch(self):
        import ast
        from pathlib import Path
        trainer=Path(__file__).with_name('genGrumpyPGPE.py').read_text(encoding='utf-8')
        script=Path(__file__).with_name('run_genesis_binpack.ps1').read_text(encoding='utf-8')
        tree=ast.parse(trainer)
        constants={target.id: stmt.value.value for stmt in tree.body if isinstance(stmt,ast.Assign)
                   for target in stmt.targets if isinstance(target,ast.Name)
                   if isinstance(stmt.value,ast.Constant)}
        self.assertEqual(constants['CK_FORMAT'],'picogen-grumpy-1680-pgpe-cp-only-val-selected-v3')
        self.assertIn("'generation','distribution','optimizer'",trainer)
        self.assertIn("'adam','best','best_anchor'",trainer)
        self.assertIn("'numpy_rng','torch_rng'",trainer)
        self.assertIn('best.grumpy-pgpe-v3.latest.pt',script)
        self.assertIn("$NnueArgs += @('--resume',$Checkpoint)",script)
        self.assertIn('only an increase in --generations is allowed',script)
        self.assertIn('SaveTrainingLock\n } elseif',script)
        self.assertIn("if ($ResumeNnue) {",script)
        self.assertIn('Cannot resume NNUE: complete checkpoint not found',script)
        self.assertIn('MILESTONE G',trainer)

if __name__=='__main__': unittest.main()
