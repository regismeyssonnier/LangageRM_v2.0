#!/usr/bin/env python3
# -*- coding: latin -*-

import sys
import os
import subprocess
from antlr4 import *
from llvmlite import ir, binding

try:
    from RmLangLexer import RmLangLexer
    from RmLangParser import RmLangParser
    from RmLangVisitor import RmLangVisitor
except ImportError as e:
    print("[ERREUR] " + str(e))
    print("\nRegenere les fichiers avec:")
    print("  java -jar antlr-4.13.1-complete.jar -visitor -no-listener RmLang.g4")
    sys.exit(1)

class CompilateurLLVM(RmLangVisitor):
    
    def __init__(self):
        # LLVM
        self.module = ir.Module(name="mon_programme")
        self.builder = None
        self.variables = {}
        self.fonctions = {}
        self.classes = {}
        self.constructeurs = {}
        self.struct_types = {}
        self.vtable_types = {}
        self.vtable_vars = {}
        self.class_ids = {}
        self.class_id_to_name = {}
        self.next_class_id = 1
        self.method_indices = {}
        
        # Contexte
        self.fonction_courante = None
        self.classe_courante = None
        self.objet_courant = None
        self.return_value = None
        
        # Compteurs
        self._str_count = 0
        self._label_count = 0
        
        # Types LLVM
        self.i8 = ir.IntType(8)
        self.i32 = ir.IntType(32)
        self.double = ir.DoubleType()
        self.void = ir.VoidType()
        self.string_type = ir.PointerType(self.i8)
        self.void_ptr = ir.PointerType(self.i8)
        
        # Déclarer les fonctions C
        self._declare_printf()
        self._declare_puts()
        self._declare_malloc()
        self._declare_free()
        self._declare_chkstk()

        self.var_types = {}   # clean_nom -> nom de classe déclarée
    
    def _clean_name(self, name):
        if name is None:
            return "var"
        clean = ''.join(c for c in name if c.isalnum() or c == '_')
        if not clean or clean[0].isdigit():
            clean = "v" + clean
        return clean
    
    def _declare_chkstk(self):
        chkstk_ty = ir.FunctionType(self.void, [])
        self.chkstk = ir.Function(self.module, chkstk_ty, name="__chkstk")
        entry = self.chkstk.append_basic_block("entry")
        builder = ir.IRBuilder(entry)
        builder.ret_void()
    
    def _declare_printf(self):
        printf_ty = ir.FunctionType(self.i32, [self.string_type], var_arg=True)
        self.printf = ir.Function(self.module, printf_ty, name="printf")
    
    def _declare_puts(self):
        puts_ty = ir.FunctionType(self.i32, [self.string_type])
        self.puts = ir.Function(self.module, puts_ty, name="puts")
    
    def _declare_malloc(self):
        malloc_ty = ir.FunctionType(self.void_ptr, [self.i32])
        self.malloc = ir.Function(self.module, malloc_ty, name="malloc")
    
    def _declare_free(self):
        free_ty = ir.FunctionType(self.void, [self.void_ptr])
        self.free = ir.Function(self.module, free_ty, name="free")
    
    def _create_string(self, text):
        self._str_count += 1
        name = "str_" + str(self._str_count)
        bytes_text = bytearray(text.encode('utf-8') + b'\x00')
        const_array = ir.Constant(ir.ArrayType(self.i8, len(bytes_text)), bytes_text)
        var = ir.GlobalVariable(self.module, const_array.type, name=name)
        var.initializer = const_array
        var.global_constant = True
        return var
    
    def _get_llvm_type(self, type_rm):
        if type_rm == 'int':
            return self.i32
        elif type_rm == 'double':
            return self.double
        elif type_rm == 'bool':
            return self.i32
        elif type_rm == 'string':
            return self.string_type
        else:
            return self.void_ptr
    
    def _is_float(self, val):
        return isinstance(val.type, ir.DoubleType)
    
    def _is_int(self, val):
        return isinstance(val.type, ir.IntType)
    
    def _to_double(self, val):
        if self._is_int(val):
            return self.builder.sitofp(val, self.double)
        return val
    
    def _arith(self, gauche, droite, int_op, float_op):
        if self._is_float(gauche) or self._is_float(droite):
            gauche = self._to_double(gauche)
            droite = self._to_double(droite)
            return getattr(self.builder, float_op)(gauche, droite, name="")
        return getattr(self.builder, int_op)(gauche, droite, name="")
    
    def _compare(self, gauche, droite, op):
        if self._is_float(gauche) or self._is_float(droite):
            gauche = self._to_double(gauche)
            droite = self._to_double(droite)
            cmp = self.builder.fcmp_ordered(op, gauche, droite)
        else:
            cmp = self.builder.icmp_signed(op, gauche, droite)
        return self.builder.zext(cmp, self.i32, name="")
    
    def _to_bool(self, val):
        if self._is_float(val):
            zero = ir.Constant(self.double, 0.0)
            return self.builder.fcmp_ordered('!=', val, zero)
        zero = ir.Constant(self.i32, 0)
        return self.builder.icmp_signed('!=', val, zero)
    
    def _get_class_id(self, classe):
        if classe not in self.class_ids:
            self.class_ids[classe] = self.next_class_id
            self.class_id_to_name[self.next_class_id] = classe
            self.next_class_id += 1
        return self.class_ids[classe]
    
    def _get_method_index(self, classe, methode):
        if classe not in self.method_indices:
            self.method_indices[classe] = {}
        if methode not in self.method_indices[classe]:
            self.method_indices[classe][methode] = len(self.method_indices[classe])
        return self.method_indices[classe][methode]
    
    def _get_vtable_type(self, classe):
        if classe in self.vtable_types:
            return self.vtable_types[classe]
        
        methodes = self.classes[classe]['methodes']
        types = [self.i32]
        
        for nom, info in methodes.items():
            type_retour = info['type_retour']
            param_types = info['param_types']
            
            return_type = self._get_llvm_type(type_retour) if type_retour != 'void' else self.void
            param_types_llvm = [self.void_ptr]
            for p in param_types:
                param_types_llvm.append(self._get_llvm_type(p))
            
            func_type = ir.FunctionType(return_type, param_types_llvm)
            func_ptr_type = ir.PointerType(func_type)
            types.append(func_ptr_type)
        
        vtable_type = ir.LiteralStructType(types)
        self.vtable_types[classe] = vtable_type
        return vtable_type
    
    def _get_struct_type(self, classe):
        if classe in self.struct_types:
            return self.struct_types[classe]
        
        membres = self.classes[classe]['membres']
        types = [self.void_ptr]
        for m in membres:
            t = self._get_llvm_type(m['type'])
            types.append(t)
        struct_type = ir.LiteralStructType(types)
        self.struct_types[classe] = struct_type
        return struct_type
    
    def _creer_vtable(self, classe):
        vtable_type = self._get_vtable_type(classe)
        if vtable_type is None:
            return None
        
        vtable_name = "vtable_" + classe
        
        if vtable_name in self.vtable_vars:
            return self.vtable_vars[vtable_name]
        
        vtable_var = ir.GlobalVariable(self.module, vtable_type, name=vtable_name)
        
        methodes = self.classes[classe]['methodes']
        values = []
        
        class_id = self._get_class_id(classe)
        class_id_const = ir.Constant(self.i32, class_id)
        values.append(class_id_const)
        
        for nom, info in methodes.items():
            func = self._creer_fonction_methode(classe, nom, info)
            values.append(func)
        
        vtable_var.initializer = ir.Constant(vtable_type, values)
        vtable_var.global_constant = True
        
        self.vtable_vars[vtable_name] = vtable_var
        return vtable_var
    
    def _creer_fonction_methode(self, classe, nom, info):
        type_retour = info['type_retour']
        params = info['params']
        param_types = info['param_types']
    
        return_type = self._get_llvm_type(type_retour) if type_retour != 'void' else self.void
        param_types_llvm = [self.void_ptr]
        for p in param_types:
            param_types_llvm.append(self._get_llvm_type(p))
    
        func_type = ir.FunctionType(return_type, param_types_llvm)
        func_name = self._clean_name(classe + "_" + nom)
        func = ir.Function(self.module, func_type, name=func_name)
    
        func.args[0].name = "this"
        for i, p_name in enumerate(params):
            func.args[i + 1].name = self._clean_name(p_name)
    
        entry_block = func.append_basic_block("entry")
        old_builder = self.builder
        old_vars = dict(self.variables)
        old_var_types = dict(self.var_types)  # Sauvegarder
        old_obj = self.objet_courant
        old_classe = self.classe_courante
    
        self.builder = ir.IRBuilder(entry_block)
        self.variables = {}
        self.var_types = {}  # Réinitialiser
        self.objet_courant = func.args[0]
        self.classe_courante = classe
    
        # Enregistrer le type de 'this'
        self.var_types['this'] = classe
    
        for i, p_name in enumerate(params):
            clean_name = self._clean_name(p_name)
            llvm_type = self._get_llvm_type(param_types[i])
            ptr = self.builder.alloca(llvm_type, name=clean_name)
            self.builder.store(func.args[i + 1], ptr)
            self.variables[clean_name] = ptr
        
            # NOUVEAU: Enregistrer le type si c'est un objet
            p_type = param_types[i]
            if p_type not in ('int', 'double', 'float', 'string', 'bool', 'void'):
                self.var_types[clean_name] = p_type
    
        self.visit(info['corps'])
    
        if not self.builder.block.is_terminated:
            if type_retour == 'void':
                self.builder.ret_void()
            else:
                self.builder.ret(ir.Constant(return_type, 0))
    
        self.builder = old_builder
        self.variables = old_vars
        self.var_types = old_var_types  # Restaurer
        self.objet_courant = old_obj
        self.classe_courante = old_classe
    
        return func
    
    def _creer_objet(self, classe, args):
        struct_type = self._get_struct_type(classe)
        if struct_type is None:
            return ir.Constant(self.void_ptr, None)
    
        vtable_ptr = self._creer_vtable(classe)
        if vtable_ptr is None:
            return ir.Constant(self.void_ptr, None)
    
        td = binding.create_target_data(self.module.data_layout)
        size = struct_type.get_abi_size(td)
    
        ptr = self.builder.call(self.malloc, [ir.Constant(self.i32, size)])
        ptr = self.builder.bitcast(ptr, struct_type.as_pointer())
    
        vtable_field = self.builder.gep(ptr, [ir.Constant(self.i32, 0), ir.Constant(self.i32, 0)])
        vtable_ptr_cast = self.builder.bitcast(vtable_ptr, self.void_ptr)
        self.builder.store(vtable_ptr_cast, vtable_field)
    
        for i in range(len(self.classes[classe]['membres'])):
            field_ptr = self.builder.gep(ptr, [ir.Constant(self.i32, 0), ir.Constant(self.i32, i + 1)])
            m_type = self.classes[classe]['membres'][i]['type']
            if m_type == 'int':
                self.builder.store(ir.Constant(self.i32, 0), field_ptr)
            elif m_type == 'double':
                self.builder.store(ir.Constant(self.double, 0.0), field_ptr)
            elif m_type == 'string':
                empty = self._create_string("")
                self.builder.store(self.builder.bitcast(empty, self.string_type), field_ptr)
            elif m_type == 'bool':
                self.builder.store(ir.Constant(self.i32, 0), field_ptr)
    
        # NOUVEAU: Enregistrer la classe de l'objet dans var_types
        clean_ptr = "obj_" + str(id(ptr))
        self.var_types[clean_ptr] = classe
    
        if classe in self.constructeurs:
            old_obj = self.objet_courant
            old_vars = dict(self.variables)
            old_var_types = dict(self.var_types)
            old_classe = self.classe_courante
        
            self.objet_courant = ptr
            self.classe_courante = classe
            self.var_types['this'] = classe
        
            constructeur = self.constructeurs[classe]
            param_names = constructeur['param_names']
            param_types = constructeur.get('param_types', [])
        
            for i, p_name in enumerate(param_names):
                if i < len(args):
                    p_type = param_types[i] if i < len(param_types) else 'int'
                    llvm_type = self._get_llvm_type(p_type)
                    clean_name = self._clean_name(p_name)
                    param_ptr = self.builder.alloca(llvm_type, name=clean_name)
                    self.builder.store(args[i], param_ptr)
                    self.variables[clean_name] = param_ptr
                    # Enregistrer le type du parametre
                    if p_type not in ('int', 'double', 'float', 'string', 'bool', 'void'):
                        self.var_types[clean_name] = p_type
        
            self.visit(constructeur['corps'])
        
            self.variables = old_vars
            self.var_types = old_var_types
            self.objet_courant = old_obj
            self.classe_courante = old_classe
    
        return self.builder.bitcast(ptr, self.void_ptr)
    
    def _resoudre_objet(self, nom):
        if nom == 'this':
            return self.objet_courant
        clean_nom = self._clean_name(nom)
        if clean_nom in self.variables:
            ptr = self.variables[clean_nom]
            return self.builder.load(ptr)
        return None
    
    def _get_field_index(self, classe, champ):
        membres = self.classes[classe]['membres']
        for i, m in enumerate(membres):
            if m['nom'] == champ:
                return i + 1
        return -1
    
    def _store_field(self, obj_ptr, classe, champ, valeur):
        idx = self._get_field_index(classe, champ)
        if idx == -1:
            return
        struct_type = self._get_struct_type(classe)
        if struct_type is None:
            return
        obj_struct = self.builder.bitcast(obj_ptr, struct_type.as_pointer())
        field_ptr = self.builder.gep(obj_struct, [ir.Constant(self.i32, 0), ir.Constant(self.i32, idx)])
        self.builder.store(valeur, field_ptr)
    
    def _load_field(self, obj_ptr, classe, champ):
        idx = self._get_field_index(classe, champ)
        if idx == -1:
            return ir.Constant(self.i32, 0)
        struct_type = self._get_struct_type(classe)
        if struct_type is None:
            return ir.Constant(self.i32, 0)
        obj_struct = self.builder.bitcast(obj_ptr, struct_type.as_pointer())
        field_ptr = self.builder.gep(obj_struct, [ir.Constant(self.i32, 0), ir.Constant(self.i32, idx)])
        return self.builder.load(field_ptr)
    
    def _call_method(self, obj_ptr, methode, args):
        classe = self.classe_courante
        if classe is None:
            return ir.Constant(self.i32, 0)
        
        struct_type = self._get_struct_type(classe)
        if struct_type is None:
            return ir.Constant(self.i32, 0)
        
        obj_struct = self.builder.bitcast(obj_ptr, struct_type.as_pointer())
        vtable_ptr_ptr = self.builder.gep(obj_struct, [ir.Constant(self.i32, 0), ir.Constant(self.i32, 0)])
        vtable_ptr = self.builder.load(vtable_ptr_ptr)
        
        method_index = self._get_method_index(classe, methode)
        vtable_index = method_index + 1
        
        vtable_type = self._get_vtable_type(classe)
        vtable_struct = self.builder.bitcast(vtable_ptr, vtable_type.as_pointer())
        func_ptr_ptr = self.builder.gep(vtable_struct, [ir.Constant(self.i32, 0), ir.Constant(self.i32, vtable_index)])
        func_ptr = self.builder.load(func_ptr_ptr)
        
        call_args = [obj_ptr] + args
        return self.builder.call(func_ptr, call_args)
    
    # ============================================================
    # PROGRAMME
    # ============================================================
    
    def visitProgram(self, ctx):
        for child in ctx.getChildren():
            self.visit(child)
        
        if 'main' not in self.fonctions:
            main_type = ir.FunctionType(self.i32, [])
            main_func = ir.Function(self.module, main_type, name="main")
            entry_block = main_func.append_basic_block("entry")
            old_builder = self.builder
            self.builder = ir.IRBuilder(entry_block)
            self.builder.ret(ir.Constant(self.i32, 0))
            self.builder = old_builder
        
        return None
    
    # ============================================================
    # DECLARATIONS
    # ============================================================
    
    def visitDeclaration(self, ctx):
        type_var = ctx.type_().getText()
        nom = ctx.ID(0).getText()
        
        if self.classe_courante is not None:
            if self.classe_courante not in self.classes:
                self.classes[self.classe_courante] = {'membres': [], 'methodes': {}}
            self.classes[self.classe_courante]['membres'].append({
                'nom': nom,
                'type': type_var
            })
            return None
        
        llvm_type = self._get_llvm_type(type_var)
        clean_nom = self._clean_name(nom)
        ptr = self.builder.alloca(llvm_type, name=clean_nom)
        self.variables[clean_nom] = ptr

        if type_var not in ('int', 'double', 'float', 'string', 'bool', 'void'):
            self.var_types[clean_nom] = type_var   # NOUVEAU
        
        if ctx.expression():
            valeur = self.visit(ctx.expression())
            self.builder.store(valeur, ptr)
        else:
            if type_var == 'int':
                self.builder.store(ir.Constant(self.i32, 0), ptr)
            elif type_var == 'double':
                self.builder.store(ir.Constant(self.double, 0.0), ptr)
            elif type_var == 'bool':
                self.builder.store(ir.Constant(self.i32, 0), ptr)
            elif type_var == 'string':
                empty = self._create_string("")
                self.builder.store(self.builder.bitcast(empty, self.string_type), ptr)
            else:
                self.builder.store(ir.Constant(self.void_ptr, None), ptr)
        
        return ptr
    
    # ============================================================
    # FONCTIONS
    # ============================================================
    
    def visitFonction(self, ctx):
        type_retour = ctx.type_().getText() if ctx.type_() else 'void'
        nom = ctx.ID().getText()
        self.fonction_courante = nom
    
        params = []
        param_names = []
        param_types = []
        if ctx.param_list():
            for param in ctx.param_list().param():
                p_type = param.type_().getText()
                p_name = param.ID().getText()
                params.append(p_type + " " + p_name)
                param_names.append(p_name)
                param_types.append(p_type)
    
        return_type = self._get_llvm_type(type_retour) if type_retour != 'void' else self.void
        param_types_llvm = [self._get_llvm_type(p) for p in param_types]
    
        func_type = ir.FunctionType(return_type, param_types_llvm)
        clean_nom = self._clean_name(nom)
        func = ir.Function(self.module, func_type, name=clean_nom)
        self.fonctions[clean_nom] = func
    
        for i, arg in enumerate(func.args):
            if i < len(param_names):
                arg.name = self._clean_name(param_names[i])
    
        entry_block = func.append_basic_block("entry")
        old_builder = self.builder
        old_vars = dict(self.variables)
        old_var_types = dict(self.var_types)  # Sauvegarder
    
        self.builder = ir.IRBuilder(entry_block)
        self.variables = {}
        self.var_types = {}  # Réinitialiser pour la fonction
    
        for i, arg in enumerate(func.args):
            if i < len(param_names):
                p_type = param_types[i] if i < len(param_types) else 'int'
                llvm_type = self._get_llvm_type(p_type)
                clean_pname = self._clean_name(param_names[i])
                ptr = self.builder.alloca(llvm_type, name=clean_pname)
                self.builder.store(arg, ptr)
                self.variables[clean_pname] = ptr
            
                # NOUVEAU: Enregistrer le type si c'est un objet
                if p_type not in ('int', 'double', 'float', 'string', 'bool', 'void'):
                    self.var_types[clean_pname] = p_type
    
        self.visit(ctx.bloc())
    
        if not self.builder.block.is_terminated:
            if type_retour == 'void':
                self.builder.ret_void()
            else:
                self.builder.ret(ir.Constant(return_type, 0))
    
        self.builder = old_builder
        self.variables = old_vars
        self.var_types = old_var_types  # Restaurer
        self.fonction_courante = None
    
        return func
    
    def visitRetour(self, ctx):
        if ctx.expression():
            valeur = self.visit(ctx.expression())
            self.builder.ret(valeur)
        else:
            self.builder.ret_void()
    
    # ============================================================
    # CLASSES
    # ============================================================
    
    def visitClasse(self, ctx):
        nom = ctx.ID().getText()
        self.classe_courante = nom
        
        if nom not in self.classes:
            self.classes[nom] = {'membres': [], 'methodes': {}}
        
        for membre in ctx.class_member():
            self.visit(membre)
        
        self.classe_courante = None
        return None
    
    def visitConstructeur(self, ctx):
        nom = ctx.ID().getText()
        params = []
        param_names = []
        param_types = []
        if ctx.param_list():
            for param in ctx.param_list().param():
                p_type = param.type_().getText()
                p_name = param.ID().getText()
                params.append(p_type + " " + p_name)
                param_names.append(p_name)
                param_types.append(p_type)
        
        self.constructeurs[nom] = {
            'params': params,
            'param_names': param_names,
            'param_types': param_types,
            'corps': ctx.bloc()
        }
        
        return None
    
    def visitFonction_membre(self, ctx):
        type_retour = ctx.type_().getText() if ctx.type_() else 'void'
        nom = ctx.ID().getText()
        
        params = []
        param_names = []
        param_types = []
        if ctx.param_list():
            for param in ctx.param_list().param():
                p_type = param.type_().getText()
                p_name = param.ID().getText()
                params.append(p_type + " " + p_name)
                param_names.append(p_name)
                param_types.append(p_type)
        
        if self.classe_courante in self.classes:
            self.classes[self.classe_courante]['methodes'][nom] = {
                'type_retour': type_retour,
                'params': params,
                'param_names': param_names,
                'param_types': param_types,
                'corps': ctx.bloc()
            }
        
        return None
    
    def _resoudre_classe(self, nom):
        if nom == 'this':
            return self.classe_courante
        clean_nom = self._clean_name(nom)
        return self.var_types.get(clean_nom, self.classe_courante)

    def visitMethod_call(self, ctx):
        obj_nom = ctx.objectRef().getText()
        methode = ctx.ID().getText()
        args = []
        if ctx.argument_list():
            for expr in ctx.argument_list().expression():
                args.append(self.visit(expr))

        obj_ptr = self._resoudre_objet(obj_nom)
        if obj_ptr is None:
            return None

        classe = self._resoudre_classe(obj_nom)     # REMPLACE l'ancienne logique
        if classe is None:
            return None

        old_classe = self.classe_courante
        self.classe_courante = classe
        result = self._call_method(obj_ptr, methode, args)
        self.classe_courante = old_classe
        return result
    
    # ============================================================
    # INSTRUCTIONS
    # ============================================================
    
    def visitBloc(self, ctx):
        for instr in ctx.instruction():
            self.visit(instr)
            if self.builder.block.is_terminated:
                break
    
    def visitAffectation(self, ctx):
        nom = ctx.ID().getText()
        clean_nom = self._clean_name(nom)
        valeur = self.visit(ctx.expression())
        ptr = self.variables.get(clean_nom)
        if ptr:
            self.builder.store(valeur, ptr)
        return valeur
    
    def visitAffectation_membre(self, ctx):
        obj_nom = ctx.objectRef().getText()
        champ = ctx.ID().getText()
        valeur = self.visit(ctx.expression())

        obj_ptr = self._resoudre_objet(obj_nom)
        if obj_ptr is None:
            return None

        classe = self._resoudre_classe(obj_nom)     # REMPLACE self.classe_courante
        if classe is None:
            return None

        self._store_field(obj_ptr, classe, champ, valeur)
        return valeur
    
    def visitAppel_fonction(self, ctx):
        nom = ctx.ID().getText()
        args = []
        if ctx.argument_list():
            for expr in ctx.argument_list().expression():
                args.append(self.visit(expr))
    
        clean_nom = self._clean_name(nom)
    
        if clean_nom in self.fonctions:
            func = self.fonctions[clean_nom]
            return self.builder.call(func, args)
    
        if nom in self.classes:
            return self._creer_objet(nom, args)
    
        return None
    
    def visitCondition(self, ctx):
        nb_conditions = len(ctx.expression())
        end_block = self.builder.append_basic_block("if_end")
        
        for i in range(nb_conditions):
            condition = self.visit(ctx.expression(i))
            zero = ir.Constant(self.i32, 0)
            cond = self.builder.icmp_signed('!=', condition, zero)
            
            then_block = self.builder.append_basic_block("if_then_" + str(i))
            next_block = self.builder.append_basic_block("if_next_" + str(i))
            
            self.builder.cbranch(cond, then_block, next_block)
            
            self.builder.position_at_start(then_block)
            self.visit(ctx.bloc(i))
            if not self.builder.block.is_terminated:
                self.builder.branch(end_block)
            
            self.builder.position_at_start(next_block)
        
        if ctx.ELSE():
            self.visit(ctx.bloc(nb_conditions))
            if not self.builder.block.is_terminated:
                self.builder.branch(end_block)
        else:
            if not self.builder.block.is_terminated:
                self.builder.branch(end_block)
        
        self.builder.position_at_start(end_block)
    
    def visitBoucle_while(self, ctx):
        cond_block = self.builder.append_basic_block("while_cond")
        body_block = self.builder.append_basic_block("while_body")
        end_block = self.builder.append_basic_block("while_end")

        self.builder.branch(cond_block)

        self.builder.position_at_start(cond_block)
        condition = self.visit(ctx.expression())
        cond = self._to_bool(condition)
        self.builder.cbranch(cond, body_block, end_block)

        self.builder.position_at_start(body_block)
        self.visit(ctx.bloc())
        if not self.builder.block.is_terminated:
            self.builder.branch(cond_block)

        self.builder.position_at_start(end_block)
        return None
    
    def visitBoucle_for(self, ctx):
        if ctx.for_init():
            self.visit(ctx.for_init())

        cond_block = self.builder.append_basic_block("for_cond")
        body_block = self.builder.append_basic_block("for_body")
        inc_block = self.builder.append_basic_block("for_inc")
        end_block = self.builder.append_basic_block("for_end")

        self.builder.branch(cond_block)

        self.builder.position_at_start(cond_block)
        if ctx.expression(0):
            condition = self.visit(ctx.expression(0))
            cond = self._to_bool(condition)
            self.builder.cbranch(cond, body_block, end_block)
        else:
            self.builder.branch(body_block)

        self.builder.position_at_start(body_block)
        self.visit(ctx.bloc())
        if not self.builder.block.is_terminated:
            self.builder.branch(inc_block)

        self.builder.position_at_start(inc_block)
        if ctx.expression(1):
            self.visit(ctx.expression(1))
        self.builder.branch(cond_block)

        self.builder.position_at_start(end_block)
        return None
    
    def visitForDecl(self, ctx):
        type_var = ctx.type_().getText()
        nom = ctx.ID().getText()
        
        llvm_type = self._get_llvm_type(type_var)
        clean_nom = self._clean_name(nom)
        ptr = self.builder.alloca(llvm_type, name=clean_nom)
        self.variables[clean_nom] = ptr
        
        if ctx.expression():
            valeur = self.visit(ctx.expression())
            self.builder.store(valeur, ptr)
        else:
            if type_var == 'int':
                self.builder.store(ir.Constant(self.i32, 0), ptr)
            elif type_var == 'double':
                self.builder.store(ir.Constant(self.double, 0.0), ptr)
            else:
                self.builder.store(ir.Constant(self.i32, 0), ptr)
        
        return ptr
    
    def visitForExprInit(self, ctx):
        return self.visit(ctx.expression())
    
    # ============================================================
    # EXPRESSIONS - AVEC DISPATCH DE TYPE
    # ============================================================
    
    def visitIntLiteral(self, ctx):
        return ir.Constant(self.i32, int(ctx.getText()))
    
    def visitFloatLiteral(self, ctx):
        return ir.Constant(self.double, float(ctx.getText()))
    
    def visitStringLiteral(self, ctx):
        text = ctx.getText()[1:-1]
        str_var = self._create_string(text)
        return self.builder.bitcast(str_var, self.string_type)
    
    def visitBoolLiteral(self, ctx):
        value = 1 if ctx.getText() == 'true' else 0
        return ir.Constant(self.i32, value)
    
    def visitVarRef(self, ctx):
        nom = ctx.ID().getText()
        clean_nom = self._clean_name(nom)
        ptr = self.variables.get(clean_nom)
        if ptr:
            return self.builder.load(ptr)
        return ir.Constant(self.i32, 0)
    
    def visitAddExpr(self, ctx):
        gauche = self.visit(ctx.expression(0))
        droite = self.visit(ctx.expression(1))
        return self._arith(gauche, droite, 'add', 'fadd')
    
    def visitSubExpr(self, ctx):
        gauche = self.visit(ctx.expression(0))
        droite = self.visit(ctx.expression(1))
        return self._arith(gauche, droite, 'sub', 'fsub')
    
    def visitMulExpr(self, ctx):
        gauche = self.visit(ctx.expression(0))
        droite = self.visit(ctx.expression(1))
        return self._arith(gauche, droite, 'mul', 'fmul')
    
    def visitDivExpr(self, ctx):
        gauche = self.visit(ctx.expression(0))
        droite = self.visit(ctx.expression(1))
        return self._arith(gauche, droite, 'sdiv', 'fdiv')
    
    def visitModExpr(self, ctx):
        gauche = self.visit(ctx.expression(0))
        droite = self.visit(ctx.expression(1))
        return self._arith(gauche, droite, 'srem', 'frem')
    
    def visitEqualExpr(self, ctx):
        return self._compare(self.visit(ctx.expression(0)), self.visit(ctx.expression(1)), '==')
    
    def visitNotEqualExpr(self, ctx):
        return self._compare(self.visit(ctx.expression(0)), self.visit(ctx.expression(1)), '!=')
    
    def visitLessExpr(self, ctx):
        return self._compare(self.visit(ctx.expression(0)), self.visit(ctx.expression(1)), '<')
    
    def visitGreaterExpr(self, ctx):
        return self._compare(self.visit(ctx.expression(0)), self.visit(ctx.expression(1)), '>')
    
    def visitLessOrEqualExpr(self, ctx):
        return self._compare(self.visit(ctx.expression(0)), self.visit(ctx.expression(1)), '<=')
    
    def visitGreaterOrEqualExpr(self, ctx):
        return self._compare(self.visit(ctx.expression(0)), self.visit(ctx.expression(1)), '>=')
    
    def visitAndExpr(self, ctx):
        gauche = self.visit(ctx.expression(0))
        droite = self.visit(ctx.expression(1))
        result = self.builder.and_(self._to_bool(gauche), self._to_bool(droite))
        return self.builder.zext(result, self.i32, name="")
    
    def visitOrExpr(self, ctx):
        gauche = self.visit(ctx.expression(0))
        droite = self.visit(ctx.expression(1))
        result = self.builder.or_(self._to_bool(gauche), self._to_bool(droite))
        return self.builder.zext(result, self.i32, name="")
    
    def visitNotExpr(self, ctx):
        valeur = self.visit(ctx.expression())
        cmp = self._to_bool(valeur)
        inv = self.builder.not_(cmp)
        return self.builder.zext(inv, self.i32, name="")
    
    def visitParensExpr(self, ctx):
        return self.visit(ctx.expression())
    
    def visitThisExpr(self, ctx):
        return self.objet_courant
    
    def visitMemberAccessExpr(self, ctx):
        obj_nom = ctx.objectRef().getText()
        champ = ctx.ID().getText()

        obj_ptr = self._resoudre_objet(obj_nom)
        if obj_ptr is None:
            return ir.Constant(self.i32, 0)

        classe = self._resoudre_classe(obj_nom)     # REMPLACE self.classe_courante
        if classe is None:
            return ir.Constant(self.i32, 0)

        return self._load_field(obj_ptr, classe, champ)
    
    def visitMethodCallExpr(self, ctx):
        obj_nom = ctx.objectRef().getText()
        methode = ctx.ID().getText()
        args = []
        if ctx.argument_list():
            for expr in ctx.argument_list().expression():
                args.append(self.visit(expr))
        
        obj_ptr = self._resoudre_objet(obj_nom)
        if obj_ptr is None:
            return ir.Constant(self.i32, 0)
        
        classe = self.classe_courante
        if classe is None:
            if self.classes:
                classe = list(self.classes.keys())[0]
            else:
                return ir.Constant(self.i32, 0)
        
        old_classe = self.classe_courante
        self.classe_courante = classe
        
        result = self._call_method(obj_ptr, methode, args)
        
        self.classe_courante = old_classe
        
        return result
    
    def visitCallExpr(self, ctx):
        nom = ctx.ID().getText()
        args = []
        if ctx.argument_list():
            for expr in ctx.argument_list().expression():
                args.append(self.visit(expr))
    
        clean_nom = self._clean_name(nom)
    
        if clean_nom in self.fonctions:
            func = self.fonctions[clean_nom]
            return self.builder.call(func, args)
    
        if nom in self.classes:
            return self._creer_objet(nom, args)
    
        return ir.Constant(self.i32, 0)
    
    def visitAssignExpr(self, ctx):
        nom = ctx.expression(0).getText()
        clean_nom = self._clean_name(nom)
        valeur = self.visit(ctx.expression(1))
        ptr = self.variables.get(clean_nom)
        if ptr:
            self.builder.store(valeur, ptr)
        return valeur
    
    def visitRefOfExpr(self, ctx):
        nom = ctx.ID().getText()
        clean_nom = self._clean_name(nom)
        ptr = self.variables.get(clean_nom)
        if ptr:
            return ptr
        return ir.Constant(self.i32, 0)
    
    def visitArgument_list(self, ctx):
        return [self.visit(expr) for expr in ctx.expression()]
    
    # ============================================================
    # PRINT
    # ============================================================
    
    def visitPrint_stmt(self, ctx):
        valeur = self.visit(ctx.expression())
        
        if isinstance(valeur.type, ir.IntType) and valeur.type.width == 32:
            fmt = self._create_string("%d")
            fmt_ptr = self.builder.bitcast(fmt, self.string_type)
            self.builder.call(self.printf, [fmt_ptr, valeur])
        elif isinstance(valeur.type, ir.DoubleType):
            fmt = self._create_string("%f")
            fmt_ptr = self.builder.bitcast(fmt, self.string_type)
            self.builder.call(self.printf, [fmt_ptr, valeur])
        elif isinstance(valeur.type, ir.PointerType):
            self.builder.call(self.printf, [valeur])
        else:
            self.builder.call(self.printf, [valeur])
        
        return None
    
    def visitPrintln_stmt(self, ctx):
        valeur = self.visit(ctx.expression())
        
        if isinstance(valeur.type, ir.IntType) and valeur.type.width == 32:
            fmt = self._create_string("%d\n")
            fmt_ptr = self.builder.bitcast(fmt, self.string_type)
            self.builder.call(self.printf, [fmt_ptr, valeur])
        elif isinstance(valeur.type, ir.DoubleType):
            fmt = self._create_string("%f\n")
            fmt_ptr = self.builder.bitcast(fmt, self.string_type)
            self.builder.call(self.printf, [fmt_ptr, valeur])
        elif isinstance(valeur.type, ir.PointerType):
            self.builder.call(self.puts, [valeur])
        else:
            self.builder.call(self.puts, [valeur])
        
        return None

# ============================================================
# COMPILATION
# ============================================================

def compiler_rm(fichier_source):
    with open(fichier_source, 'r', encoding='utf-8') as f:
        code = f.read()
    
    print("[FICHIER] " + fichier_source)
    print("=" * 60)
    
    input_stream = InputStream(code)
    lexer = RmLangLexer(input_stream)
    stream = CommonTokenStream(lexer)
    parser = RmLangParser(stream)
    tree = parser.program()
    
    print("Compilation en LLVM IR...")
    compilateur = CompilateurLLVM()
    compilateur.visit(tree)
    
    nom_base = os.path.splitext(fichier_source)[0]
    
    binding.initialize()
    binding.initialize_native_target()
    binding.initialize_native_asmprinter()
    
    with open(nom_base + ".ll", "w") as f:
        f.write(str(compilateur.module))
    
    print("LLVM IR genere: " + nom_base + ".ll")
    
    mod = binding.parse_assembly(str(compilateur.module))
    mod.verify()
    
    target = binding.Target.from_default_triple()
    target_machine = target.create_target_machine()
    
    obj = target_machine.emit_object(mod)
    with open(nom_base + ".o", "wb") as f:
        f.write(obj)
    
    print("Fichier objet: " + nom_base + ".o")
    
    print("Edition des liens...")
     
    try:
        subprocess.run(["clang", nom_base + ".o", "-o", nom_base + ".exe"], check=True)
        print("Compilation avec clang: " + nom_base + ".exe")
    except:
        try:
            subprocess.run(["gcc", "-mno-stack-arg-probe", nom_base + ".o", "-o", nom_base + ".exe"], check=True)
            print("Compilation avec gcc: " + nom_base + ".exe")
        except:
            print("Erreur: ni clang ni gcc n'est disponible")
            return
    
    print("\n[SUCCES] Executable genere: " + nom_base + ".exe")
    print("Fichiers generes: " + nom_base + ".ll, " + nom_base + ".o, " + nom_base + ".exe")
    print("\nPour executer: ./" + nom_base + ".exe")

# ============================================================
# MAIN
# ============================================================

def main():
    if len(sys.argv) < 2:
        print("Usage: python compile_rm.py fichier.rm")
        sys.exit(1)
    
    try:
        compiler_rm(sys.argv[1])
    except Exception as e:
        print("[ERREUR] " + str(e))
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()