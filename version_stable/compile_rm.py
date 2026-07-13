#!/usr/bin/env python3
# -*- coding: latin -*-

import sys
import os
import re
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
        self.en_scan_classe = False
        
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
        self._declare_scanf()


        self.var_types = {}   # clean_nom -> nom de classe déclarée

        self.arrays = {}  # clean_nom -> {'type': type, 'size': size, 'ptr': ptr}
        self.array_types = {}  # clean_nom -> type element

        # FILE* fopen(const char* filename, const char* mode)
        fopen_ty = ir.FunctionType(self.void_ptr, [self.string_type, self.string_type])
        self.fopen = ir.Function(self.module, fopen_ty, name="fopen")
    
        # int fclose(FILE* stream)
        fclose_ty = ir.FunctionType(self.i32, [self.void_ptr])
        self.fclose = ir.Function(self.module, fclose_ty, name="fclose")
    
        # char* fgets(char* buffer, int size, FILE* stream)
        fgets_ty = ir.FunctionType(self.string_type, [self.string_type, self.i32, self.void_ptr])
        self.fgets = ir.Function(self.module, fgets_ty, name="fgets")
    
        # int fprintf(FILE* stream, const char* format, ...)
        fprintf_ty = ir.FunctionType(self.i32, [self.void_ptr, self.string_type], var_arg=True)
        self.fprintf = ir.Function(self.module, fprintf_ty, name="fprintf")
    
        # int fscanf(FILE* stream, const char* format, ...)
        fscanf_ty = ir.FunctionType(self.i32, [self.void_ptr, self.string_type], var_arg=True)
        self.fscanf = ir.Function(self.module, fscanf_ty, name="fscanf")
    
        # Supprimer un fichier : int remove(const char* filename)
        remove_ty = ir.FunctionType(self.i32, [self.string_type])
        self.remove_func = ir.Function(self.module, remove_ty, name="remove")
    
        # Renommer un fichier : int rename(const char* old, const char* new)
        rename_ty = ir.FunctionType(self.i32, [self.string_type, self.string_type])
        self.rename_func = ir.Function(self.module, rename_ty, name="rename")
    
        # Gestion des fichiers ouverts
        self.file_handles = {}  # nom_variable -> pointeur FILE*

        # size_t fread(void* ptr, size_t size, size_t count, FILE* stream)
        fread_ty = ir.FunctionType(self.i32, [self.void_ptr, self.i32, self.i32, self.void_ptr])
        self.fread = ir.Function(self.module, fread_ty, name="fread")
    
        # size_t fwrite(const void* ptr, size_t size, size_t count, FILE* stream)
        fwrite_ty = ir.FunctionType(self.i32, [self.void_ptr, self.i32, self.i32, self.void_ptr])
        self.fwrite = ir.Function(self.module, fwrite_ty, name="fwrite")
    
        # int fseek(FILE* stream, long offset, int whence)
        # SEEK_SET = 0, SEEK_CUR = 1, SEEK_END = 2
        fseek_ty = ir.FunctionType(self.i32, [self.void_ptr, self.i32, self.i32])
        self.fseek = ir.Function(self.module, fseek_ty, name="fseek")
    
        # long ftell(FILE* stream)
        ftell_ty = ir.FunctionType(self.i32, [self.void_ptr])
        self.ftell = ir.Function(self.module, ftell_ty, name="ftell")
    
        # void rewind(FILE* stream)
        rewind_ty = ir.FunctionType(self.void, [self.void_ptr])
        self.rewind = ir.Function(self.module, rewind_ty, name="rewind")
    
        # int feof(FILE* stream)
        feof_ty = ir.FunctionType(self.i32, [self.void_ptr])
        self.feof = ir.Function(self.module, feof_ty, name="feof")

        # Ajouter fputs
        fputs_ty = ir.FunctionType(self.i32, [self.string_type, self.void_ptr])
        self.fputs = ir.Function(self.module, fputs_ty, name="fputs")

        self.file_read_buffer = None
    
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

    def _declare_scanf(self):
        """Déclare la fonction scanf de la librairie C"""
        # int scanf(const char* format, ...)
        scanf_ty = ir.FunctionType(self.i32, [self.string_type], var_arg=True)
        self.scanf = ir.Function(self.module, scanf_ty, name="scanf")
    
    def _create_string(self, text):
        self._str_count += 1
        name = "str_" + str(self._str_count)
    
        # Gérer les échappements
        text = text.replace('\\n', '\n')
        text = text.replace('\\t', '\t')
        text = text.replace('\\r', '\r')
        text = text.replace('\\\\', '\\')
        text = text.replace('\\"', '"')
    
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
        elif type_rm == 'char':
            return self.i8  # i8 = 1 octet
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
        if classe in self.method_indices and methode in self.method_indices[classe]:
            return self.method_indices[classe][methode]
        # Ne devrait plus jamais arriver, mais on garde un filet de sécurité
        print(f"[WARN] _get_method_index: {classe}.{methode} non pré-indexée, index arbitraire")
        if classe not in self.method_indices:
            self.method_indices[classe] = {}
        idx = len(self.method_indices[classe])
        self.method_indices[classe][methode] = idx
        return idx
    
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
            elem_type = self._get_llvm_type(m['type'])
            t = ir.ArrayType(elem_type, m.get('array_size', 1)) if m.get('is_array') else elem_type
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
        param_names = info['param_names']    # déjà présent dans info, juste pas utilisé
        param_types = info['param_types']

        return_type = self._get_llvm_type(type_retour) if type_retour != 'void' else self.void
        param_types_llvm = [self.void_ptr]
        for p in param_types:
            param_types_llvm.append(self._get_llvm_type(p))

        func_type = ir.FunctionType(return_type, param_types_llvm)
        func_name = self._clean_name(classe + "_" + nom)
        func = ir.Function(self.module, func_type, name=func_name)

        func.args[0].name = "this"
        for i, p_name in enumerate(param_names):        # CORRIGÉ : param_names
            func.args[i + 1].name = self._clean_name(p_name)

        entry_block = func.append_basic_block("entry")
        old_builder = self.builder
        old_vars = dict(self.variables)
        old_var_types = dict(self.var_types)
        old_obj = self.objet_courant
        old_classe = self.classe_courante

        self.builder = ir.IRBuilder(entry_block)
        self.variables = {}
        self.var_types = {}
        self.objet_courant = func.args[0]
        self.classe_courante = classe

        self.var_types['this'] = classe

        for i, p_name in enumerate(param_names):        # CORRIGÉ : param_names
            clean_name = self._clean_name(p_name)
            llvm_type = self._get_llvm_type(param_types[i])
            ptr = self.builder.alloca(llvm_type, name=clean_name)
            self.builder.store(func.args[i + 1], ptr)
            self.variables[clean_name] = ptr

            p_type = param_types[i]
            if p_type not in ('int', 'double', 'float', 'string', 'bool', 'char', 'void'):
                self.var_types[clean_name] = p_type

        self.visit(info['corps'])

        if not self.builder.block.is_terminated:
            if type_retour == 'void':
                self.builder.ret_void()
            else:
                self.builder.ret(ir.Constant(return_type, 0))

        self.builder = old_builder
        self.variables = old_vars
        self.var_types = old_var_types
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
            membre = self.classes[classe]['membres'][i]
            m_type = membre['type']

            if membre.get('is_array'):
                elem_type = self._get_llvm_type(m_type)
                for j in range(membre.get('array_size', 1)):
                    elem_ptr = self.builder.gep(field_ptr, [ir.Constant(self.i32, 0), ir.Constant(self.i32, j)])
                    zero_val = ir.Constant(self.double, 0.0) if isinstance(elem_type, ir.DoubleType) else ir.Constant(elem_type, 0)
                    self.builder.store(zero_val, elem_ptr)
                continue
    
            if m_type == 'int':
                self.builder.store(ir.Constant(self.i32, 0), field_ptr)
            elif m_type == 'double':
                self.builder.store(ir.Constant(self.double, 0.0), field_ptr)
            elif m_type == 'string':
                empty = self._create_string("")
                self.builder.store(self.builder.bitcast(empty, self.string_type), field_ptr)
            elif m_type == 'bool':
                self.builder.store(ir.Constant(self.i32, 0), field_ptr)
            elif m_type == 'char':
                # ============================================================
                # GESTION DES CARACTÈRES (char)
                # ============================================================
                self.builder.store(ir.Constant(self.i8, 0), field_ptr)
            else:
                # Objet ou autre type
                self.builder.store(ir.Constant(self.void_ptr, None), field_ptr)
    
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
                    if p_type not in ('int', 'double', 'float', 'string', 'bool', 'char', 'void'):
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
    
    def _get_membre_info(self, classe, champ):
        for m in self.classes[classe]['membres']:
            if m['nom'] == champ:
                return m
        return None

    def _load_field(self, obj_ptr, classe, champ):
        idx = self._get_field_index(classe, champ)
        if idx == -1:
            return ir.Constant(self.i32, 0)
        struct_type = self._get_struct_type(classe)
        obj_struct = self.builder.bitcast(obj_ptr, struct_type.as_pointer())
        field_ptr = self.builder.gep(obj_struct, [ir.Constant(self.i32, 0), ir.Constant(self.i32, idx)])

        membre = self._get_membre_info(classe, champ)
        if membre and membre.get('is_array'):
            zero = ir.Constant(self.i32, 0)
            return self.builder.gep(field_ptr, [zero, zero])   # décayage en i8*

        return self.builder.load(field_ptr)
    
    def _call_method(self, obj_ptr, methode, args):
        """
        [CORRIGÉ - VERSION FINALE]
        """
        # 1. Vérifications
        if obj_ptr is None:
            print("[ERREUR] _call_method: obj_ptr est None")
            return ir.Constant(self.i32, 0)

        classe = self.classe_courante
        if classe is None or classe not in self.classes:
            print(f"[ERREUR] _call_method: classe invalide '{classe}'")
            return ir.Constant(self.i32, 0)

        if methode not in self.classes[classe]['methodes']:
            print(f"[ERREUR] Méthode '{methode}' non trouvée")
            return ir.Constant(self.i32, 0)

        # 2. Infos de la méthode
        info_methode = self.classes[classe]['methodes'][methode]
        nb_params_attendus = len(info_methode.get('params', []))
        param_types = info_methode.get('param_types', [])

        print(f"[DEBUG] _call_method: {classe}.{methode}() - attendu={nb_params_attendus}, fourni={len(args)}")

        # 3. Ajuster les arguments utilisateur (sans this)
        args_ajustes = []
        for i in range(nb_params_attendus):
            if i < len(args):
                args_ajustes.append(args[i])
            else:
                # Valeur par défaut selon le type
                if i < len(param_types):
                    p_type = param_types[i]
                    if p_type == 'int':
                        args_ajustes.append(ir.Constant(self.i32, 0))
                    elif p_type in ('double', 'float'):
                        args_ajustes.append(ir.Constant(self.double, 0.0))
                    elif p_type == 'bool':
                        args_ajustes.append(ir.Constant(self.i32, 0))
                    elif p_type == 'char':
                        args_ajustes.append(ir.Constant(self.i8, 0))
                    elif p_type == 'string':
                        empty = self._create_string("")
                        args_ajustes.append(self.builder.bitcast(empty, self.string_type))
                    else:
                        args_ajustes.append(ir.Constant(self.void_ptr, None))
                else:
                    args_ajustes.append(ir.Constant(self.i32, 0))

        # 4. Récupérer le struct type et la vtable
        struct_type = self._get_struct_type(classe)
        obj_struct = self.builder.bitcast(obj_ptr, struct_type.as_pointer())
    
        vtable_ptr_ptr = self.builder.gep(
            obj_struct, 
            [ir.Constant(self.i32, 0), ir.Constant(self.i32, 0)]
        )
        vtable_ptr = self.builder.load(vtable_ptr_ptr)

        # 5. Récupérer le pointeur de fonction
        method_index = self._get_method_index(classe, methode)
        vtable_index = method_index + 1

        vtable_type = self._get_vtable_type(classe)
        vtable_struct = self.builder.bitcast(vtable_ptr, vtable_type.as_pointer())
        func_ptr_ptr = self.builder.gep(
            vtable_struct,
            [ir.Constant(self.i32, 0), ir.Constant(self.i32, vtable_index)]
        )
        func_ptr = self.builder.load(func_ptr_ptr)

        # 6. CORRECTION : call_args = [obj_ptr] + args_ajustes
        call_args = [obj_ptr] + args_ajustes
    
        nb_total = 1 + nb_params_attendus
    
        print(f"[DEBUG] _call_method: call_args={len(call_args)} (attendu={nb_total})")
        print(f"[DEBUG]   Types: {[str(a.type) for a in call_args]}")

        # 7. Vérification finale
        if len(call_args) != nb_total:
            print(f"[ERREUR FATALE] Nombre d'arguments incorrect: {len(call_args)} vs {nb_total}")
            print(f"   => Troncature à {nb_total}")
            call_args = call_args[:nb_total]

        # 8. Appel
        try:
            result = self.builder.call(func_ptr, call_args)
            return result
        except Exception as e:
            print(f"[ERREUR] Exception dans l'appel: {e}")
            return ir.Constant(self.i32, 0)

    # ============================================================
    # 
    #      NOUVELLES FONCTIONS : OPÉRATEURS BINAIRES           
    #
    # ============================================================
    
    def _bitwise_cast_to_same_width(self, gauche, droite):
        """
        [NOUVEAU] Convertit deux entiers à la même largeur pour les opérations binaires.
        """
        if gauche.type.width < droite.type.width:
            gauche = self.builder.sext(gauche, droite.type)
        elif droite.type.width < gauche.type.width:
            droite = self.builder.sext(droite, gauche.type)
        return gauche, droite
    
    def _ensure_int(self, val, nom_operateur):
        """
        [NOUVEAU] Vérifie qu'une valeur est un entier, lève une erreur sinon.
        """
        if not self._is_int(val):
            raise TypeError(f"L'opérateur '{nom_operateur}' nécessite des opérandes entières")
        return val
    
    # ============================================================
    # VISITEURS DES OPÉRATEURS BINAIRES
    # ============================================================
    
    def visitBitwiseNotExpr(self, ctx):
        """
        [NOUVEAU] ~expression
        Complément à 1 (inverse tous les bits)
        """
        valeur = self.visit(ctx.expression())
        self._ensure_int(valeur, '~')
        
        # ~x = x ^ -1 (XOR avec tous les bits à 1)
        masque = ir.Constant(valeur.type, -1)
        return self.builder.xor(valeur, masque)
    
    def visitLeftShiftExpr(self, ctx):
        """
        [NOUVEAU] expression << expression
        Décalage gauche
        """
        gauche = self.visit(ctx.expression(0))
        droite = self.visit(ctx.expression(1))
        
        self._ensure_int(gauche, '<<')
        self._ensure_int(droite, '<<')
        
        gauche, droite = self._bitwise_cast_to_same_width(gauche, droite)
        return self.builder.shl(gauche, droite)
    
    def visitRightShiftExpr(self, ctx):
        """
        [NOUVEAU] expression >> expression
        Décalage droite arithmétique (préserve le signe)
        """
        gauche = self.visit(ctx.expression(0))
        droite = self.visit(ctx.expression(1))
        
        self._ensure_int(gauche, '>>')
        self._ensure_int(droite, '>>')
        
        gauche, droite = self._bitwise_cast_to_same_width(gauche, droite)
        return self.builder.ashr(gauche, droite)
    
    def visitBitwiseAndExpr(self, ctx):
        """
        [NOUVEAU] expression & expression
        ET binaire
        """
        gauche = self.visit(ctx.expression(0))
        droite = self.visit(ctx.expression(1))
        
        self._ensure_int(gauche, '&')
        self._ensure_int(droite, '&')
        
        gauche, droite = self._bitwise_cast_to_same_width(gauche, droite)
        return self.builder.and_(gauche, droite)
    
    def visitBitwiseXorExpr(self, ctx):
        """
        [NOUVEAU] expression ^ expression
        OU exclusif binaire (XOR)
        """
        gauche = self.visit(ctx.expression(0))
        droite = self.visit(ctx.expression(1))
        
        self._ensure_int(gauche, '^')
        self._ensure_int(droite, '^')
        
        gauche, droite = self._bitwise_cast_to_same_width(gauche, droite)
        return self.builder.xor(gauche, droite)
    
    def visitBitwiseOrExpr(self, ctx):
        """
        [NOUVEAU] expression | expression
        OU binaire
        """
        gauche = self.visit(ctx.expression(0))
        droite = self.visit(ctx.expression(1))
        
        self._ensure_int(gauche, '|')
        self._ensure_int(droite, '|')
        
        gauche, droite = self._bitwise_cast_to_same_width(gauche, droite)
        return self.builder.or_(gauche, droite)
    
    # ============================================================
    # VISITEUR CORRIGÉ POUR LES AFFECTATIONS COMPOSÉES
    # ============================================================

    def visitSimpleCompoundAssign(self, ctx):
        """
        [NOUVEAU - CORRIGÉ] Gère: a += 5;  a &= 0xFF;  a <<= 1;
        """
        nom_var = ctx.ID().getText()
        operateur = ctx.COMPOUND_ASSIGN().getText()
        droite_val = self.visit(ctx.expression())
    
        clean_nom = self._clean_name(nom_var)
    
        print(f"[DEBUG] CompoundAssign: {nom_var} {operateur} (valeur droite: {droite_val})")
    
        if clean_nom in self.variables:
            ptr = self.variables[clean_nom]
        
            # Charger la valeur actuelle
            valeur_actuelle = self.builder.load(ptr)
            print(f"[DEBUG]   Valeur actuelle: {valeur_actuelle}")
        
            # Appliquer l'opération
            nouvelle_valeur = self._appliquer_operation_composee(
                valeur_actuelle, droite_val, operateur
            )
            print(f"[DEBUG]   Nouvelle valeur: {nouvelle_valeur}")
        
            # Stocker le résultat
            self.builder.store(nouvelle_valeur, ptr)
            return nouvelle_valeur
    
        print(f"[DEBUG]   Variable '{clean_nom}' non trouvée!")
        return droite_val


    def visitArrayCompoundAssign(self, ctx):
        """
        [NOUVEAU - CORRIGÉ] Gère: tab[i] += 5;  tab[i] |= mask;
        """
        nom_array = ctx.ID().getText()
        index = self.visit(ctx.expression(0))
        operateur = ctx.COMPOUND_ASSIGN().getText()
        droite_val = self.visit(ctx.expression(1))
    
        clean_nom = self._clean_name(nom_array)
    
        print(f"[DEBUG] ArrayCompoundAssign: {nom_array}[index] {operateur} {droite_val}")
    
        if clean_nom in self.variables:
            ptr = self.variables[clean_nom]
        
            # Calculer l'adresse de l'élément
            if isinstance(ptr.type.pointee, ir.ArrayType):
                elem_ptr = self.builder.gep(ptr, [ir.Constant(self.i32, 0), index])
                valeur_actuelle = self.builder.load(elem_ptr)
            
                nouvelle_valeur = self._appliquer_operation_composee(
                    valeur_actuelle, droite_val, operateur
                )
            
                # Conversion pour char si nécessaire
                if isinstance(elem_ptr.type.pointee, ir.IntType) and elem_ptr.type.pointee.width == 8:
                    if isinstance(nouvelle_valeur.type, ir.IntType) and nouvelle_valeur.type.width == 32:
                        nouvelle_valeur = self.builder.trunc(nouvelle_valeur, self.i8)
            
                self.builder.store(nouvelle_valeur, elem_ptr)
                return nouvelle_valeur
    
        return droite_val


    def _appliquer_operation_composee(self, gauche, droite, operateur):
        """
        [CORRIGÉ] Applique l'opération composée avec gestion correcte des types.
        """
        print(f"[DEBUG] _appliquer_operation_composee: gauche={gauche}, droite={droite}, op={operateur}")
        print(f"[DEBUG]   Type gauche: {gauche.type}, Type droite: {droite.type}")
    
        # Ajuster les types si les deux sont des entiers
        if self._is_int(gauche) and self._is_int(droite):
            if gauche.type.width != droite.type.width:
                if gauche.type.width < droite.type.width:
                    gauche = self.builder.sext(gauche, droite.type)
                else:
                    droite = self.builder.sext(droite, gauche.type)
    
        # Opérations arithmétiques
        if operateur == '+=':
            if self._is_float(gauche) or self._is_float(droite):
                return self.builder.fadd(self._to_double(gauche), self._to_double(droite))
            return self.builder.add(gauche, droite)
    
        elif operateur == '-=':
            if self._is_float(gauche) or self._is_float(droite):
                return self.builder.fsub(self._to_double(gauche), self._to_double(droite))
            return self.builder.sub(gauche, droite)
    
        elif operateur == '*=':
            if self._is_float(gauche) or self._is_float(droite):
                return self.builder.fmul(self._to_double(gauche), self._to_double(droite))
            return self.builder.mul(gauche, droite)
    
        elif operateur == '/=':
            if self._is_float(gauche) or self._is_float(droite):
                return self.builder.fdiv(self._to_double(gauche), self._to_double(droite))
            return self.builder.sdiv(gauche, droite)
    
        elif operateur == '%=':
            if self._is_float(gauche) or self._is_float(droite):
                return self.builder.frem(self._to_double(gauche), self._to_double(droite))
            return self.builder.srem(gauche, droite)
    
        #========================================================
        #   OPÉRATIONS BINAIRES (CORRIGÉES)    
        # =======================================================
    
        elif operateur == '&=':
            if not self._is_int(gauche) or not self._is_int(droite):
                raise TypeError("&= nécessite des entiers")
            return self.builder.and_(gauche, droite)
    
        elif operateur == '|=':
            if not self._is_int(gauche) or not self._is_int(droite):
                raise TypeError("|= nécessite des entiers")
            return self.builder.or_(gauche, droite)
    
        elif operateur == '^=':
            if not self._is_int(gauche) or not self._is_int(droite):
                raise TypeError("^= nécessite des entiers")
            return self.builder.xor(gauche, droite)
    
        elif operateur == '<<=':
            if not self._is_int(gauche) or not self._is_int(droite):
                raise TypeError("<<= nécessite des entiers")
            return self.builder.shl(gauche, droite)
    
        elif operateur == '>>=':
            if not self._is_int(gauche) or not self._is_int(droite):
                raise TypeError(">>= nécessite des entiers")
            return self.builder.ashr(gauche, droite)
    
        else:
            raise NotImplementedError(f"Opérateur composé inconnu : {operateur}")
    
    # ============================================================
    # FONCTIONS SPÉCIALES POUR MANIPULATIONS DE BITS
    # ============================================================
    
    def _bit_test(self, valeur, position):
        """
        [NOUVEAU] Teste si le bit à 'position' est 1.
        Équivalent C: (valeur >> position) & 1
        Retourne un i1 (booléen LLVM)
        """
        decale = self.builder.lshr(valeur, ir.Constant(valeur.type, position))
        masque = ir.Constant(valeur.type, 1)
        resultat = self.builder.and_(decale, masque)
        return self.builder.trunc(resultat, ir.IntType(1))
    
    def _bit_set(self, valeur, position):
        """
        [NOUVEAU] Met le bit à 'position' à 1.
        Équivalent C: valeur | (1 << position)
        """
        un = ir.Constant(valeur.type, 1)
        masque = self.builder.shl(un, ir.Constant(valeur.type, position))
        return self.builder.or_(valeur, masque)
    
    def _bit_clear(self, valeur, position):
        """
        [NOUVEAU] Met le bit à 'position' à 0.
        Équivalent C: valeur & ~(1 << position)
        """
        un = ir.Constant(valeur.type, 1)
        masque = self.builder.shl(un, ir.Constant(valeur.type, position))
        masque_inverse = self.builder.xor(masque, ir.Constant(valeur.type, -1))
        return self.builder.and_(valeur, masque_inverse)
    
    def _bit_toggle(self, valeur, position):
        """
        [NOUVEAU] Inverse le bit à 'position'.
        Équivalent C: valeur ^ (1 << position)
        """
        un = ir.Constant(valeur.type, 1)
        masque = self.builder.shl(un, ir.Constant(valeur.type, position))
        return self.builder.xor(valeur, masque)
    
    # ============================================================
    # VISITEUR POUR L'AFFECTATION COMPOSÉE (INSTRUCTION)
    # ============================================================
    
    def visitAffectation_composee(self, ctx):
        """
        [NOUVEAU] Instruction: a += 5; ou tab[i] &= mask;
        """
        operateur = ctx.COMPOUND_ASSIGN().getText()
        droite_val = self.visit(ctx.expression(len(ctx.expression()) - 1))
        
        # Cas 1: Variable simple
        if ctx.ID() and not ctx.expression(0) if hasattr(ctx, 'expression') else True:
            nom_var = ctx.ID().getText()
            clean_nom = self._clean_name(nom_var)
            
            if clean_nom in self.variables:
                ptr = self.variables[clean_nom]
                valeur_actuelle = self.builder.load(ptr)
                nouvelle_valeur = self._appliquer_operation_composee(
                    valeur_actuelle, droite_val, operateur
                )
                self.builder.store(nouvelle_valeur, ptr)
        
        # Cas 2: Tableau (tab[index] OP= valeur)
        elif hasattr(ctx, 'expression') and len(ctx.expression()) > 1:
            nom_array = ctx.ID().getText()
            clean_nom = self._clean_name(nom_array)
            index = self.visit(ctx.expression(0))
            
            if clean_nom in self.variables:
                ptr = self.variables[clean_nom]
                
                if isinstance(ptr.type.pointee, ir.ArrayType):
                    elem_ptr = self.builder.gep(ptr, [ir.Constant(self.i32, 0), index])
                    valeur_actuelle = self.builder.load(elem_ptr)
                    nouvelle_valeur = self._appliquer_operation_composee(
                        valeur_actuelle, droite_val, operateur
                    )
                    if isinstance(elem_ptr.type.pointee, ir.IntType) and elem_ptr.type.pointee.width == 8:
                        if isinstance(nouvelle_valeur.type, ir.IntType) and nouvelle_valeur.type.width == 32:
                            nouvelle_valeur = self.builder.trunc(nouvelle_valeur, self.i8)
                    self.builder.store(nouvelle_valeur, elem_ptr)
    
    # ============================================================
    # PROGRAMME
    # ============================================================
    
    def visitProgram(self, ctx):
        declarations_globales = []
        autres = []

        for child in ctx.getChildren():
            if isinstance(child, RmLangParser.DeclarationContext):
                declarations_globales.append(child)
            else:
                autres.append(child)

        # Visiter les globales EN PREMIER, pendant que builder est encore None
        for decl in declarations_globales:
            self.visit(decl)

        # Puis les fonctions et classes
        for child in autres:
            self.visit(child)

        # Créer la fonction main si elle n'existe pas
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
    
    def _get_original_text(self, ctx):
        """Récupère le texte source EXACT (avec espaces) entre le début et la fin du contexte"""
        start_index = ctx.start.start
        stop_index = ctx.stop.stop
        input_stream = ctx.start.getInputStream()
        return input_stream.getText(start_index, stop_index)

    def visitDeclaration(self, ctx):
        if ctx.REF():
            type_var = ctx.type_().getText()
            nom = ctx.ID(0).getText()        # "z"
            ref_nom = ctx.ID(1).getText()    # "w"

            clean_nom = self._clean_name(nom)
            clean_ref = self._clean_name(ref_nom)

            if clean_ref in self.variables:
                # z devient un ALIAS : on stocke directement le pointeur de w
                self.variables[clean_nom] = self.variables[clean_ref]
            return None

        type_var = ctx.type_().getText()
        nom = ctx.ID(0).getText()

        print(f"[DEBUG] visitDeclaration: type={type_var}, nom={nom}, builder={self.builder is not None}")

        if self.en_scan_classe:
            if self.classe_courante not in self.classes:
                self.classes[self.classe_courante] = {'membres': [], 'methodes': {}}

            texte = self._get_original_text(ctx)
            is_array = bool(re.search(r'\b' + re.escape(nom) + r'\s*\[', texte))
            array_size = 1
            if is_array:
                m = re.search(r'\[([^\]]+)\]', texte)
                if m:
                    try:
                        array_size = int(m.group(1))
                    except:
                        array_size = 256

            self.classes[self.classe_courante]['membres'].append({
                'nom': nom, 'type': type_var,
                'is_array': is_array, 'array_size': array_size
            })
            return None

        clean_nom = self._clean_name(nom)
        texte = self._get_original_text(ctx)

        # Détection tableau
        
        pattern = r'\b' + re.escape(nom) + r'\s*\['
        est_tableau = bool(re.search(pattern, texte))

        if est_tableau:
            # Extraire la taille
            match = re.search(r'\[([^\]]+)\]', texte)
            taille_val = 5
            if match:
                try:
                    taille_val = int(match.group(1))
                except:
                    taille_val = 5

            # Extraire les valeurs
            match_init = re.search(r'\{([^}]*)\}', texte)
            valeurs_init = []

            if match_init:
                content = match_init.group(1).strip()
                if content:
                    parts = []
                    current = ""
                    in_string = False
                    for c in content:
                        if c == '"':
                            in_string = not in_string
                            current += c
                        elif c == ',' and not in_string:
                            parts.append(current.strip())
                            current = ""
                        else:
                            current += c
                    if current.strip():
                        parts.append(current.strip())

                    for v in parts:
                        v = v.strip()
                        if not v:
                            continue

                        if type_var == 'string':
                            if v.startswith('"') and v.endswith('"'):
                                str_var = self._create_string(v[1:-1])
                                if self.builder:
                                    valeurs_init.append(self.builder.bitcast(str_var, self.string_type))
                                else:
                                    zero = ir.Constant(self.i32, 0)
                                    valeurs_init.append(str_var.gep([zero, zero]))
                            else:
                                empty = self._create_string("")
                                if self.builder:
                                    valeurs_init.append(self.builder.bitcast(empty, self.string_type))
                                else:
                                    zero = ir.Constant(self.i32, 0)
                                    valeurs_init.append(empty.gep([zero, zero]))
                        elif type_var == 'int':
                            if v.isdigit():
                                valeurs_init.append(ir.Constant(self.i32, int(v)))
                            else:
                                valeurs_init.append(ir.Constant(self.i32, 0))
                        elif type_var == 'double':
                            try:
                                valeurs_init.append(ir.Constant(self.double, float(v)))
                            except:
                                valeurs_init.append(ir.Constant(self.double, 0.0))
                        elif type_var == 'bool':
                            valeurs_init.append(ir.Constant(self.i32, 1 if v == 'true' else 0))
                        elif type_var == 'char':
                            if v.startswith("'") and v.endswith("'"):
                                char_val = ord(v[1:-1])
                                valeurs_init.append(ir.Constant(self.i8, char_val))
                            elif v.isdigit():
                                valeurs_init.append(ir.Constant(self.i8, int(v)))
                            else:
                                valeurs_init.append(ir.Constant(self.i8, 0))
                        else:
                            valeurs_init.append(ir.Constant(self.void_ptr, None))

            if valeurs_init:
                taille_val = len(valeurs_init)

            # Créer le tableau
            elem_type = self._get_llvm_type(type_var)
            array_type = ir.ArrayType(elem_type, taille_val)

            if self.builder is None:
                # Variable globale
                global_array = ir.GlobalVariable(self.module, array_type, name=clean_nom)
                init_values = []
                for i in range(taille_val):
                    if i < len(valeurs_init):
                        init_values.append(valeurs_init[i])
                    else:
                        if type_var == 'int':
                            init_values.append(ir.Constant(self.i32, 0))
                        elif type_var == 'double':
                            init_values.append(ir.Constant(self.double, 0.0))
                        elif type_var == 'string':
                            empty = self._create_string("")
                            zero = ir.Constant(self.i32, 0)
                            init_values.append(empty.gep([zero, zero]))
                        elif type_var == 'char':
                            init_values.append(ir.Constant(self.i8, 0))
                        else:
                            init_values.append(ir.Constant(self.void_ptr, None))
                global_array.initializer = ir.Constant(array_type, init_values)
                self.variables[clean_nom] = global_array
                self.array_types[clean_nom] = type_var
                return global_array

            # Tableau local
            ptr = self.builder.alloca(array_type, name=clean_nom)
        
            # Si c'est un tableau de char, on le stocke aussi comme string pour faciliter l'accès
            if type_var == 'char':
                # Créer un pointeur vers le tableau (decay en i8*)
                char_ptr = self.builder.bitcast(ptr, self.string_type)
                self.variables[clean_nom + "_ptr"] = char_ptr
        
            for i in range(taille_val):
                elem_ptr = self.builder.gep(ptr, [ir.Constant(self.i32, 0), ir.Constant(self.i32, i)])
                if i < len(valeurs_init):
                    self.builder.store(valeurs_init[i], elem_ptr)
                else:
                    if type_var == 'int':
                        self.builder.store(ir.Constant(self.i32, 0), elem_ptr)
                    elif type_var == 'double':
                        self.builder.store(ir.Constant(self.double, 0.0), elem_ptr)
                    elif type_var == 'string':
                        empty = self._create_string("")
                        self.builder.store(self.builder.bitcast(empty, self.string_type), elem_ptr)
                    elif type_var == 'char':
                        self.builder.store(ir.Constant(self.i8, 0), elem_ptr)
                    else:
                        self.builder.store(ir.Constant(self.void_ptr, None), elem_ptr)

            self.variables[clean_nom] = ptr
            self.array_types[clean_nom] = type_var
            return ptr

        # ============================================================
        # VARIABLE NORMALE
        # ============================================================

        if self.builder is None:
            llvm_type = self._get_llvm_type(type_var)
            global_var = ir.GlobalVariable(self.module, llvm_type, name=clean_nom)
            if type_var == 'int':
                global_var.initializer = ir.Constant(self.i32, 0)
            elif type_var == 'double':
                global_var.initializer = ir.Constant(self.double, 0.0)
            elif type_var == 'bool':
                global_var.initializer = ir.Constant(self.i32, 0)
            elif type_var == 'string':
                empty = self._create_string("")
                global_var.initializer = empty
            elif type_var == 'char':
                global_var.initializer = ir.Constant(self.i8, 0)
            else:
                global_var.initializer = ir.Constant(self.void_ptr, None)
            self.variables[clean_nom] = global_var
            if type_var not in ('int', 'double', 'float', 'string', 'bool', 'void', 'char'):
                self.var_types[clean_nom] = type_var
            return global_var

        llvm_type = self._get_llvm_type(type_var)
        ptr = self.builder.alloca(llvm_type, name=clean_nom)
        self.variables[clean_nom] = ptr

        if type_var not in ('int', 'double', 'float', 'string', 'bool', 'void', 'char'):
            self.var_types[clean_nom] = type_var

        # Dans la partie VARIABLE NORMALE, remplacer le bloc de conversion :

        if ctx.expression():
            valeur = self.visit(ctx.expression())
            print(f"[DEBUG] valeur={valeur}, type={type_var}")
    
            if type_var == 'string':
                if isinstance(valeur, ir.Constant) and isinstance(valeur.type, ir.IntType):
                    str_val = self._create_string(str(valeur.constant))
                    valeur = self.builder.bitcast(str_val, self.string_type)
                elif isinstance(valeur.type, ir.IntType):
                    str_val = self._create_string("0")
                    valeur = self.builder.bitcast(str_val, self.string_type)
                elif isinstance(valeur.type, ir.PointerType) and isinstance(valeur.type.pointee, ir.ArrayType):
                    # Pointeur vers tableau de char -> i8*
                    zero = ir.Constant(self.i32, 0)
                    valeur = self.builder.gep(valeur, [zero, zero])
                elif isinstance(valeur.type, ir.ArrayType) and isinstance(valeur.type.element, ir.IntType) and valeur.type.element.width == 8:
                    # Tableau de char direct -> i8*
                    zero = ir.Constant(self.i32, 0)
                    valeur = self.builder.gep(valeur, [zero, zero])
            elif type_var == 'char':
                if isinstance(valeur, ir.Constant) and isinstance(valeur.type, ir.IntType):
                    if valeur.type.width == 32:
                        valeur = self.builder.trunc(valeur, self.i8)
                elif isinstance(valeur.type, ir.IntType) and valeur.type.width == 32:
                    valeur = self.builder.trunc(valeur, self.i8)
    
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
            elif type_var == 'char':
                self.builder.store(ir.Constant(self.i8, 0), ptr)
            else:
                self.builder.store(ir.Constant(self.void_ptr, None), ptr)

        return ptr
    
    # ============================================================
    # ARRAYS
    # ============================================================
    def _get_member_array_element_ptr(self, obj_ptr, classe, champ, index):
        idx = self._get_field_index(classe, champ)
        if idx == -1:
            return None
        struct_type = self._get_struct_type(classe)
        obj_struct = self.builder.bitcast(obj_ptr, struct_type.as_pointer())
        field_ptr = self.builder.gep(obj_struct, [ir.Constant(self.i32, 0), ir.Constant(self.i32, idx)])
        zero = ir.Constant(self.i32, 0)
        return self.builder.gep(field_ptr, [zero, index])

    def visitMemberArrayAccessExpr(self, ctx):
        obj_nom = ctx.objectRef().getText()
        champ = ctx.ID().getText()
        index = self.visit(ctx.expression())
        obj_ptr = self._resoudre_objet(obj_nom)
        classe = self._resoudre_classe(obj_nom)
        if obj_ptr is None or classe is None:
            return ir.Constant(self.i32, 0)
        elem_ptr = self._get_member_array_element_ptr(obj_ptr, classe, champ, index)
        return self.builder.load(elem_ptr) if elem_ptr else ir.Constant(self.i32, 0)

    def visitAffectation_membre_tableau(self, ctx):
        obj_nom = ctx.objectRef().getText()
        champ = ctx.ID().getText()
        index = self.visit(ctx.expression(0))
        valeur = self.visit(ctx.expression(1))
        obj_ptr = self._resoudre_objet(obj_nom)
        classe = self._resoudre_classe(obj_nom)
        if obj_ptr is None or classe is None:
            return None
        elem_ptr = self._get_member_array_element_ptr(obj_ptr, classe, champ, index)
        if elem_ptr is None:
            return None
        if isinstance(elem_ptr.type.pointee, ir.IntType) and elem_ptr.type.pointee.width == 8:
            if isinstance(valeur.type, ir.IntType) and valeur.type.width == 32:
                valeur = self.builder.trunc(valeur, self.i8)
        self.builder.store(valeur, elem_ptr)
        return valeur

    def visitArrayAccessExpr(self, ctx):
        nom = ctx.ID().getText()
        clean_nom = self._clean_name(nom)
        index = self.visit(ctx.expression())
    
        if clean_nom in self.variables:
            ptr = self.variables[clean_nom]
        
            # Si c'est un pointeur vers un tableau
            if hasattr(ptr.type, 'pointee') and isinstance(ptr.type.pointee, ir.ArrayType):
                # Tableau: tab[i]
                elem_ptr = self.builder.gep(ptr, [ir.Constant(self.i32, 0), index])
                return self.builder.load(elem_ptr)
        
            # Si c'est un pointeur vers i8 (chaîne)
            elif hasattr(ptr.type, 'pointee') and isinstance(ptr.type.pointee, ir.IntType) and ptr.type.pointee.width == 8:
                # Chaîne: str[i] - retourner le caractère
                char_ptr = self.builder.gep(ptr, [index])
                return self.builder.load(char_ptr)
        
            # Si c'est un double pointeur (i8**)
            elif hasattr(ptr.type, 'pointee') and isinstance(ptr.type.pointee, ir.PointerType):
                str_ptr = self.builder.load(ptr)
                char_ptr = self.builder.gep(str_ptr, [index])
                return self.builder.load(char_ptr)
        
            else:
                return self.builder.load(ptr)
    
        return ir.Constant(self.i32, 0)

    def visitAffectation_tableau(self, ctx):
        nom = ctx.ID().getText()
        clean_nom = self._clean_name(nom)
        index = self.visit(ctx.expression(0))
        valeur = self.visit(ctx.expression(1))

        if clean_nom in self.variables:
            ptr = self.variables[clean_nom]
        
            # Vérifier le type du pointeur
            if isinstance(ptr.type, ir.PointerType):
                pointee = ptr.type.pointee
            
                # Cas 1: Tableau (ArrayType)
                if isinstance(pointee, ir.ArrayType):
                    elem_ptr = self.builder.gep(ptr, [ir.Constant(self.i32, 0), index])
                    # Si c'est un tableau de char, convertir la valeur
                    if isinstance(pointee.element, ir.IntType) and pointee.element.width == 8:
                        if isinstance(valeur.type, ir.IntType) and valeur.type.width == 32:
                            valeur = self.builder.trunc(valeur, self.i8)
                    self.builder.store(valeur, elem_ptr)
            
                # Cas 2: Pointeur vers i8 (chaîne)
                elif isinstance(pointee, ir.IntType) and pointee.width == 8:
                    char_ptr = self.builder.gep(ptr, [index])
                    if isinstance(valeur.type, ir.IntType) and valeur.type.width == 32:
                        valeur = self.builder.trunc(valeur, self.i8)
                    self.builder.store(valeur, char_ptr)
            
                # Cas 3: Double pointeur (i8**)
                elif isinstance(pointee, ir.PointerType):
                    str_ptr = self.builder.load(ptr)
                    char_ptr = self.builder.gep(str_ptr, [index])
                    if isinstance(valeur.type, ir.IntType) and valeur.type.width == 32:
                        valeur = self.builder.trunc(valeur, self.i8)
                    self.builder.store(valeur, char_ptr)
                else:
                    # Cas général
                    elem_ptr = self.builder.gep(ptr, [index])
                    self.builder.store(valeur, elem_ptr)

        return valeur

    def visitArrayLiteral(self, ctx):
        """Visite un ArrayLiteral: {1, 2, 3}"""
        valeurs = []
    
        # Parcourir tous les enfants pour trouver les expressions
        for child in ctx.getChildren():
            # Vérifier si l'enfant est une expression
            if hasattr(child, 'expression'):
                # Si c'est une expression, la visiter
                try:
                    val = self.visit(child)
                    if val is not None:
                        valeurs.append(val)
                except:
                    pass
            # Vérifier si l'enfant est un IntLiteral, FloatLiteral, etc.
            elif hasattr(child, 'getText'):
                try:
                    # Essayer de visiter l'enfant directement
                    val = self.visit(child)
                    if val is not None:
                        valeurs.append(val)
                except:
                    pass
    
        # Si on a trouvé des valeurs, les utiliser
        if valeurs:
            elem_type = valeurs[0].type
            array_type = ir.ArrayType(elem_type, len(valeurs))
            const_array = ir.Constant(array_type, valeurs)
        
            self._str_count += 1
            name = "array_lit_" + str(self._str_count)
            var = ir.GlobalVariable(self.module, array_type, name=name)
            var.initializer = const_array
            var.global_constant = True
        
            return self.builder.bitcast(var, self.void_ptr)
    
        return ir.Constant(self.void_ptr, None)
    
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
                if p_type not in ('char', 'int', 'double', 'float', 'string', 'bool', 'void'):
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
        """
        [CORRIGÉ - VERSION ROBUSTE] Gère tous les cas de return.
        """
        # Vérifier si on a une expression
        expression_ctx = ctx.expression()
    
        if expression_ctx is not None:
            # return expression;
            try:
                valeur = self.visit(expression_ctx)
            except Exception as e:
                print(f"[ERREUR] Dans return: {e}")
                valeur = None
        
            if valeur is None:
                print("[DEBUG] return: valeur est None, retourne 0 par défaut")
                # Déterminer le type de retour de la fonction
                func_type = self.builder.block.function.return_value.type
                if isinstance(func_type, ir.VoidType):
                    self.builder.ret_void()
                elif isinstance(func_type, ir.IntType):
                    self.builder.ret(ir.Constant(func_type, 0))
                elif isinstance(func_type, ir.DoubleType):
                    self.builder.ret(ir.Constant(func_type, 0.0))
                else:
                    self.builder.ret(ir.Constant(self.void_ptr, None))
                return
        
            # Si c'est un pointeur vers un tableau, le convertir
            if hasattr(valeur, 'type'):
                if isinstance(valeur.type, ir.PointerType) and isinstance(valeur.type.pointee, ir.ArrayType):
                    zero = ir.Constant(self.i32, 0)
                    valeur = self.builder.gep(valeur, [zero, zero])
        
            self.builder.ret(valeur)
        else:
            # return; sans expression
            self.builder.ret_void()
    
    # ============================================================
    # CLASSES
    # ============================================================
    
    def visitClasse(self, ctx):
        nom = ctx.ID().getText()
        self.classe_courante = nom
        self.en_scan_classe = True

        if nom not in self.classes:
            self.classes[nom] = {'membres': [], 'methodes': {}}
        
        for membre in ctx.class_member():
            self.visit(membre)
        
        self.en_scan_classe = False
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

            # NOUVEAU : assigner l'index tout de suite, dans l'ordre de déclaration
            if self.classe_courante not in self.method_indices:
                self.method_indices[self.classe_courante] = {}
            if nom not in self.method_indices[self.classe_courante]:
                idx = len(self.method_indices[self.classe_courante])
                self.method_indices[self.classe_courante][nom] = idx

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

        print(f"[DEBUG] visitMethod_call: {obj_nom}.{methode}(), args={len(args)}")

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
        """Affectation d'une variable"""
        nom = ctx.ID().getText()
        clean_nom = self._clean_name(nom)
        valeur = self.visit(ctx.expression())
        ptr = self.variables.get(clean_nom)
    
        if ptr:
            # Si c'est une chaîne (i8*) et la valeur est un entier, convertir
            if isinstance(ptr.type, ir.PointerType) and isinstance(ptr.type.pointee, ir.IntType) and ptr.type.pointee.width == 8:
                if isinstance(valeur.type, ir.IntType):
                    # Convertir l'entier en chaîne
                    str_val = self._create_string(str(valeur.constant))
                    valeur = self.builder.bitcast(str_val, self.string_type)
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
        """
        [CORRIGÉ] Gère if/else if/else correctement.
        """
        # Récupérer toutes les expressions (conditions) et tous les blocs
        expressions = ctx.expression()
        blocs = ctx.bloc()
        nb_conditions = len(expressions)
    
        # Vérifier s'il y a un else (plus de blocs que de conditions)
        has_else = ctx.ELSE() is not None
    
        # Créer le bloc de fin
        end_block = self.builder.append_basic_block("if_end")
    
        for i in range(nb_conditions):
            # Évaluer la condition
            condition = self.visit(expressions[i])
            cond = self._to_bool(condition)  # Utilise _to_bool pour gérer tous les types
        
            # Créer les blocs
            then_block = self.builder.append_basic_block(f"if_then_{i}")
        
            # Déterminer le bloc suivant
            if i == nb_conditions - 1:
                # Dernière condition
                if has_else:
                    next_block = self.builder.append_basic_block("if_else")
                else:
                    next_block = end_block
            else:
                next_block = self.builder.append_basic_block(f"if_next_{i}")
        
            # Branchement conditionnel
            self.builder.cbranch(cond, then_block, next_block)
        
            # Bloc then
            self.builder.position_at_start(then_block)
            self.visit(blocs[i])  # Utilise la liste blocs
            if not self.builder.block.is_terminated:
                self.builder.branch(end_block)
        
            # Passer au bloc suivant
            self.builder.position_at_start(next_block)
    
        # Bloc else (s'il existe)
        if has_else:
            # Le dernier bloc est le else
            else_bloc = blocs[-1]  # Dernier élément de la liste
            if else_bloc is not None:
                self.visit(else_bloc)
                if not self.builder.block.is_terminated:
                    self.builder.branch(end_block)
        else:
            # S'assurer que le bloc est terminé
            if not self.builder.block.is_terminated:
                self.builder.branch(end_block)
    
        # Positionner à la fin
        self.builder.position_at_start(end_block)
    
        return None
    
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
    
    def visitNullLiteral(self, ctx):
        """
        [NOUVEAU] Retourne un pointeur null (i8* null).
        Le littéral 'null' représente un pointeur nul.
        """
        return ir.Constant(self.void_ptr, None)

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


    def visitCharLiteral(self, ctx):
        text = ctx.getText()[1:-1]  # retire les quotes
        if text.startswith('\\'):
            # gérer les échappements courants
            mapping = {'n': '\n', 't': '\t', '\\': '\\', "'": "'", '0': '\0'}
            char = mapping.get(text[1], text[1])
        else:
            char = text
        return ir.Constant(self.i8, ord(char))
    
    def visitVarRef(self, ctx):
        nom = ctx.ID().getText()
        clean_nom = self._clean_name(nom)
        ptr = self.variables.get(clean_nom)
    
        if ptr:
            # Si c'est un tableau de char, retourner un pointeur vers le premier élément
            if isinstance(ptr.type.pointee, ir.ArrayType):
                # Vérifier si c'est un tableau de char
                if isinstance(ptr.type.pointee.element, ir.IntType) and ptr.type.pointee.element.width == 8:
                    # Retourner un pointeur vers le premier élément (i8*)
                    zero = ir.Constant(self.i32, 0)
                    return self.builder.gep(ptr, [zero, zero])
                else:
                    # Autre tableau, retourner le pointeur
                    return ptr
            # Si c'est un pointeur vers un tableau, charger le pointeur
            elif isinstance(ptr.type, ir.PointerType) and isinstance(ptr.type.pointee, ir.ArrayType):
                return ptr
            # Si c'est un double pointeur (i8**), charger le pointeur
            elif isinstance(ptr.type, ir.PointerType) and isinstance(ptr.type.pointee, ir.PointerType):
                return self.builder.load(ptr)
            # Sinon, charger la valeur
            else:
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
        
        classe = self._resoudre_classe(obj_nom)     # CORRIGÉ : utilise le vrai type déclaré
        if classe is None:
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

    def visitInputExpr(self, ctx):
        """input(type) comme expression"""
        type_attendu = 'string'  # Par défaut
    
        # Vérifier si input_type existe
        if ctx.input_type():
            type_attendu = ctx.input_type().getText()
    
        print(f"[DEBUG] input: {type_attendu}")
    
        if type_attendu == 'int':
            ptr = self.builder.alloca(self.i32, name="input_int")
            fmt = self._create_string("%d")
            fmt_ptr = self.builder.bitcast(fmt, self.string_type)
            self.builder.call(self.scanf, [fmt_ptr, ptr])
            return self.builder.load(ptr)
    
        elif type_attendu == 'double':
            ptr = self.builder.alloca(self.double, name="input_double")
            fmt = self._create_string("%lf")
            fmt_ptr = self.builder.bitcast(fmt, self.string_type)
            self.builder.call(self.scanf, [fmt_ptr, ptr])
            return self.builder.load(ptr)
    
        elif type_attendu == 'float':
            ptr = self.builder.alloca(self.double, name="input_float")
            fmt = self._create_string("%f")
            fmt_ptr = self.builder.bitcast(fmt, self.string_type)
            self.builder.call(self.scanf, [fmt_ptr, ptr])
            return self.builder.load(ptr)
    
        elif type_attendu == 'bool':
            ptr = self.builder.alloca(self.i32, name="input_bool")
            fmt = self._create_string("%d")
            fmt_ptr = self.builder.bitcast(fmt, self.string_type)
            self.builder.call(self.scanf, [fmt_ptr, ptr])
            valeur = self.builder.load(ptr)
            # Convertir en booléen (0 ou 1)
            zero = ir.Constant(self.i32, 0)
            cmp = self.builder.icmp_signed('!=', valeur, zero)
            return self.builder.zext(cmp, self.i32)
    
        else:  # string
            # Allouer un buffer de 256 caractères
            buffer_type = ir.ArrayType(self.i8, 256)
            buffer_ptr = self.builder.alloca(buffer_type, name="input_string")
            buffer_cast = self.builder.bitcast(buffer_ptr, self.string_type)
        
            fmt = self._create_string("%255s")  # Limiter à 255 caractères
            fmt_ptr = self.builder.bitcast(fmt, self.string_type)
            self.builder.call(self.scanf, [fmt_ptr, buffer_cast])
        
            return buffer_cast
    
    # ============================================================
    # PRINT
    # ============================================================
    def visitPrintln_stmt(self, ctx):
        valeur = self.visit(ctx.expression())
    
        if isinstance(valeur.type, ir.IntType):
            if valeur.type.width == 8:
                char_val = self.builder.zext(valeur, self.i32)
                fmt = self._create_string("%c\n")
                fmt_ptr = self.builder.bitcast(fmt, self.string_type)
                self.builder.call(self.printf, [fmt_ptr, char_val])
            else:
                fmt = self._create_string("%d\n")
                fmt_ptr = self.builder.bitcast(fmt, self.string_type)
                self.builder.call(self.printf, [fmt_ptr, valeur])
        elif isinstance(valeur.type, ir.DoubleType):
            fmt = self._create_string("%f\n")
            fmt_ptr = self.builder.bitcast(fmt, self.string_type)
            self.builder.call(self.printf, [fmt_ptr, valeur])
        elif isinstance(valeur.type, ir.PointerType):
            if isinstance(valeur.type.pointee, ir.IntType) and valeur.type.pointee.width == 8:
                # Utiliser printf avec %s au lieu de puts
                fmt = self._create_string("%s\n")
                fmt_ptr = self.builder.bitcast(fmt, self.string_type)
                self.builder.call(self.printf, [fmt_ptr, valeur])
            else:
                fmt = self._create_string("%p\n")
                fmt_ptr = self.builder.bitcast(fmt, self.string_type)
                addr = self.builder.bitcast(valeur, self.void_ptr)
                self.builder.call(self.printf, [fmt_ptr, addr])
        else:
            self.builder.call(self.puts, [valeur])
    
        return None

    def visitPrint_stmt(self, ctx):
        valeur = self.visit(ctx.expression())
    
        if isinstance(valeur.type, ir.IntType):
            if valeur.type.width == 8:
                char_val = self.builder.zext(valeur, self.i32)
                fmt = self._create_string("%c")
                fmt_ptr = self.builder.bitcast(fmt, self.string_type)
                self.builder.call(self.printf, [fmt_ptr, char_val])
            else:
                fmt = self._create_string("%d")
                fmt_ptr = self.builder.bitcast(fmt, self.string_type)
                self.builder.call(self.printf, [fmt_ptr, valeur])
        elif isinstance(valeur.type, ir.DoubleType):
            fmt = self._create_string("%f")
            fmt_ptr = self.builder.bitcast(fmt, self.string_type)
            self.builder.call(self.printf, [fmt_ptr, valeur])
        elif isinstance(valeur.type, ir.PointerType):
            if isinstance(valeur.type.pointee, ir.IntType) and valeur.type.pointee.width == 8:
                fmt = self._create_string("%s")
                fmt_ptr = self.builder.bitcast(fmt, self.string_type)
                self.builder.call(self.printf, [fmt_ptr, valeur])
            else:
                fmt = self._create_string("%p")
                fmt_ptr = self.builder.bitcast(fmt, self.string_type)
                addr = self.builder.bitcast(valeur, self.void_ptr)
                self.builder.call(self.printf, [fmt_ptr, addr])
        else:
            self.builder.call(self.puts, [valeur])
    
        return None

    def visitInput_stmt(self, ctx):
        """Instruction input: lit une valeur depuis l'utilisateur"""
    
        # Déterminer le type attendu
        type_attendu = 'string'  # Par défaut
        if ctx.type():
            type_attendu = ctx.type().getText()
    
        # Créer une variable pour stocker la valeur lue
        llvm_type = self._get_llvm_type(type_attendu)
        ptr = self.builder.alloca(llvm_type, name="input_var")
    
        # Créer le format string pour scanf
        if type_attendu == 'int':
            fmt = self._create_string("%d")
            fmt_ptr = self.builder.bitcast(fmt, self.string_type)
            self.builder.call(self.scanf, [fmt_ptr, ptr])
        elif type_attendu == 'double':
            fmt = self._create_string("%lf")
            fmt_ptr = self.builder.bitcast(fmt, self.string_type)
            self.builder.call(self.scanf, [fmt_ptr, ptr])
        elif type_attendu == 'string':
            # Pour les chaînes, on utilise un buffer
            # Allouer un buffer de 256 caractères
            buffer_type = ir.ArrayType(self.i8, 256)
            buffer_ptr = self.builder.alloca(buffer_type, name="input_buffer")
            buffer_cast = self.builder.bitcast(buffer_ptr, self.string_type)
        
            # Format pour chaîne: %s
            fmt = self._create_string("%s")
            fmt_ptr = self.builder.bitcast(fmt, self.string_type)
            self.builder.call(self.scanf, [fmt_ptr, buffer_cast])
        
            # Retourner le pointeur vers le buffer
            return buffer_cast
        else:
            # Par défaut: string
            buffer_type = ir.ArrayType(self.i8, 256)
            buffer_ptr = self.builder.alloca(buffer_type, name="input_buffer")
            buffer_cast = self.builder.bitcast(buffer_ptr, self.string_type)
            fmt = self._create_string("%s")
            fmt_ptr = self.builder.bitcast(fmt, self.string_type)
            self.builder.call(self.scanf, [fmt_ptr, buffer_cast])
            return buffer_cast
    
        # Charger la valeur lue
        return self.builder.load(ptr)

    # ============================================================
    # VISITEURS POUR LES OPÉRATIONS FICHIER
    # ============================================================
    def visitFile_open_stmt(self, ctx):
        """
        [MODIFIÉ] file_open("test.txt", READ);
        Retourne un i32 (FILE* casté).
        """
        nom_fichier = self.visit(ctx.expression())
        mode = ctx.file_mode().getText()
    
        mode_map = {
            'READ': 'r', 'WRITE': 'w', 'APPEND': 'a',
            'READ_BIN': 'rb', 'WRITE_BIN': 'wb',
        }
        mode_str = mode_map.get(mode, 'r')
    
        mode_var = self._create_string(mode_str)
        mode_ptr = self.builder.bitcast(mode_var, self.string_type)
    
        file_handle = self.builder.call(self.fopen, [nom_fichier, mode_ptr])
    
        null_ptr = ir.Constant(self.void_ptr, None)
        est_nul = self.builder.icmp_signed('==', file_handle, null_ptr)
    
        success_block = self.builder.append_basic_block("file_open_ok")
        error_block = self.builder.append_basic_block("file_open_error")
        continue_block = self.builder.append_basic_block("file_open_end")
    
        self.builder.cbranch(est_nul, error_block, success_block)
    
        self.builder.position_at_start(error_block)
        erreur_msg = self._create_string("Erreur: Impossible d'ouvrir le fichier\n")
        erreur_ptr = self.builder.bitcast(erreur_msg, self.string_type)
        self.builder.call(self.printf, [erreur_ptr])
        self.builder.branch(continue_block)
    
        self.builder.position_at_start(success_block)
        self.builder.branch(continue_block)
    
        self.builder.position_at_start(continue_block)
    
        # Retourner le FILE* casté en i32
        return self.builder.ptrtoint(file_handle, self.i32)


    def visitFile_close_stmt(self, ctx):
        """file_close(handle) - handle est un i32"""
        handle_as_int = self.visit(ctx.expression())
        file_handle = self.builder.inttoptr(handle_as_int, self.void_ptr)
        result = self.builder.call(self.fclose, [file_handle])
        return result


    def visitFile_write_stmt(self, ctx):
        """file_write(handle, valeur)"""
        handle_as_int = self.visit(ctx.expression(0))
        valeur = self.visit(ctx.expression(1))
        file_handle = self.builder.inttoptr(handle_as_int, self.void_ptr)
    
        if isinstance(valeur.type, ir.IntType):
            if valeur.type.width == 8:
                fmt = self._create_string("%c")
            else:
                fmt = self._create_string("%d")
        elif isinstance(valeur.type, ir.DoubleType):
            fmt = self._create_string("%f")
        else:
            fmt = self._create_string("%s")
    
        fmt_ptr = self.builder.bitcast(fmt, self.string_type)
        result = self.builder.call(self.fprintf, [file_handle, fmt_ptr, valeur])
        return result


    def visitFile_read_stmt(self, ctx):
        """file_read(handle, variable)"""
        handle_as_int = self.visit(ctx.expression())
        nom_var = ctx.ID().getText()
        clean_nom = self._clean_name(nom_var)
        file_handle = self.builder.inttoptr(handle_as_int, self.void_ptr)
    
        buffer_type = ir.ArrayType(self.i8, 1024)
        buffer_ptr = self.builder.alloca(buffer_type, name="file_read_buf")
        buffer_cast = self.builder.bitcast(buffer_ptr, self.string_type)
    
        taille = ir.Constant(self.i32, 1024)
        result = self.builder.call(self.fgets, [buffer_cast, taille, file_handle])
    
        null_ptr = ir.Constant(self.string_type, None)
        est_nul = self.builder.icmp_signed('==', result, null_ptr)
    
        success_block = self.builder.append_basic_block("file_read_ok")
        error_block = self.builder.append_basic_block("file_read_error")
        continue_block = self.builder.append_basic_block("file_read_end")
    
        self.builder.cbranch(est_nul, error_block, success_block)
    
        self.builder.position_at_start(error_block)
        if clean_nom in self.variables:
            empty = self._create_string("")
            empty_ptr = self.builder.bitcast(empty, self.string_type)
            self.builder.store(empty_ptr, self.variables[clean_nom])
        self.builder.branch(continue_block)
    
        self.builder.position_at_start(success_block)
        if clean_nom in self.variables:
            self.builder.store(buffer_cast, self.variables[clean_nom])
        self.builder.branch(continue_block)
    
        self.builder.position_at_start(continue_block)
        return result
    
    # ============================================================
    # EXPRESSIONS FICHIER (NOUVEAU)
    # ============================================================

    def visitFileOpenExpr(self, ctx):
        """
        Retourne directement le FILE* (i8*) - plus de ptrtoint !
        """
        nom_fichier = self.visit(ctx.expression())
        mode = ctx.file_mode().getText()
    
        mode_map = {
            'READ': 'r', 'WRITE': 'w', 'APPEND': 'a',
            'READ_BIN': 'rb', 'WRITE_BIN': 'wb',
        }
        mode_str = mode_map.get(mode, 'r')
    
        mode_var = self._create_string(mode_str)
        mode_ptr = self.builder.bitcast(mode_var, self.string_type)
    
        file_handle = self.builder.call(self.fopen, [nom_fichier, mode_ptr])
    
        # Vérifier erreur
        null_ptr = ir.Constant(self.void_ptr, None)
        est_nul = self.builder.icmp_signed('==', file_handle, null_ptr)
    
        success_block = self.builder.append_basic_block("file_open_ok")
        error_block = self.builder.append_basic_block("file_open_error")
        continue_block = self.builder.append_basic_block("file_open_end")
    
        self.builder.cbranch(est_nul, error_block, success_block)
    
        self.builder.position_at_start(error_block)
        erreur_msg = self._create_string("Erreur: Impossible d'ouvrir le fichier\n")
        erreur_ptr = self.builder.bitcast(erreur_msg, self.string_type)
        self.builder.call(self.printf, [erreur_ptr])
        self.builder.branch(continue_block)
    
        self.builder.position_at_start(success_block)
        self.builder.branch(continue_block)
    
        self.builder.position_at_start(continue_block)
    
        # Retourner DIRECTEMENT le FILE* (i8*) - pas de ptrtoint !
        return file_handle


    def visitFileCloseExpr(self, ctx):
        """file_close(handle) - handle est déjà i8*"""
        file_handle = self.visit(ctx.expression())  # Déjà i8*
        result = self.builder.call(self.fclose, [file_handle])
        return result


    def visitFileWriteExpr(self, ctx):
        """file_write(handle, valeur) - handle est déjà i8*"""
        file_handle = self.visit(ctx.expression(0))  # Déjà i8*
        valeur = self.visit(ctx.expression(1))
    
        if isinstance(valeur.type, ir.IntType):
            if valeur.type.width == 8:
                fmt = self._create_string("%c")
            else:
                fmt = self._create_string("%d")
            fmt_ptr = self.builder.bitcast(fmt, self.string_type)
            result = self.builder.call(self.fprintf, [file_handle, fmt_ptr, valeur])
        elif isinstance(valeur.type, ir.DoubleType):
            fmt = self._create_string("%f")
            fmt_ptr = self.builder.bitcast(fmt, self.string_type)
            result = self.builder.call(self.fprintf, [file_handle, fmt_ptr, valeur])
        else:
            # Chaîne : utiliser fputs
            result = self.builder.call(self.fputs, [valeur, file_handle])
    
        return result


    def visitFileOZOZOZReadExpr(self, ctx):
        """string s = file_read(handle) - handle est déjà i8*"""
        file_handle = self.visit(ctx.expression())  # Déjà i8*
    
        buffer_type = ir.ArrayType(self.i8, 1024)
        buffer_ptr = self.builder.alloca(buffer_type, name="file_read_buf")
        buffer_cast = self.builder.bitcast(buffer_ptr, self.string_type)
    
        taille = ir.Constant(self.i32, 1024)
        result = self.builder.call(self.fgets, [buffer_cast, taille, file_handle])
        return result

    def visitFileReadExpr(self, ctx):
        """
        string s = file_read(handle)
        Retourne une chaîne allouée avec malloc (persiste après retour).
        """
        file_handle = self.visit(ctx.expression())
    
        # Allouer avec malloc (survit au retour de fonction)
        taille = ir.Constant(self.i32, 1024)
        buffer_ptr = self.builder.call(self.malloc, [taille])
        buffer_cast = self.builder.bitcast(buffer_ptr, self.string_type)
    
        # Appeler fgets
        result = self.builder.call(self.fgets, [buffer_cast, taille, file_handle])
    
        # Chaîne vide pour EOF
        empty = self._create_string("")
        empty_ptr = self.builder.bitcast(empty, self.string_type)
    
        # Vérifier si NULL (EOF)
        null_ptr = ir.Constant(self.string_type, None)
        est_nul = self.builder.icmp_signed('==', result, null_ptr)
    
        eof_block = self.builder.append_basic_block("read_eof")
        ok_block = self.builder.append_basic_block("read_ok")
        end_block = self.builder.append_basic_block("read_end")
    
        self.builder.cbranch(est_nul, eof_block, ok_block)
    
        self.builder.position_at_start(eof_block)
        self.builder.branch(end_block)
    
        self.builder.position_at_start(ok_block)
        self.builder.branch(end_block)
    
        self.builder.position_at_start(end_block)
        phi = self.builder.phi(self.string_type)
        phi.add_incoming(empty_ptr, eof_block)    # "" si EOF
        phi.add_incoming(buffer_cast, ok_block)    # ligne lue sinon
    
        return phi


    def visitFile_close_stmt(self, ctx):
        """file_close(handle) - handle est déjà i8*"""
        file_handle = self.visit(ctx.expression())  # Déjà i8*
        result = self.builder.call(self.fclose, [file_handle])
        return result


    def visitFile_write_stmt(self, ctx):
        """file_write(handle, valeur) - handle est déjà i8*"""
        file_handle = self.visit(ctx.expression(0))  # Déjà i8*
        valeur = self.visit(ctx.expression(1))
    
        if isinstance(valeur.type, ir.IntType):
            if valeur.type.width == 8:
                fmt = self._create_string("%c")
            else:
                fmt = self._create_string("%d")
            fmt_ptr = self.builder.bitcast(fmt, self.string_type)
            result = self.builder.call(self.fprintf, [file_handle, fmt_ptr, valeur])
        elif isinstance(valeur.type, ir.DoubleType):
            fmt = self._create_string("%f")
            fmt_ptr = self.builder.bitcast(fmt, self.string_type)
            result = self.builder.call(self.fprintf, [file_handle, fmt_ptr, valeur])
        else:
            result = self.builder.call(self.fputs, [valeur, file_handle])
    
        return result


    def visitFile_read_stmt(self, ctx):
        """file_read(handle, variable) - handle est déjà i8*"""
        file_handle = self.visit(ctx.expression())  # Déjà i8*
        nom_var = ctx.ID().getText()
        clean_nom = self._clean_name(nom_var)
    
        buffer_type = ir.ArrayType(self.i8, 1024)
        buffer_ptr = self.builder.alloca(buffer_type, name="file_read_buf")
        buffer_cast = self.builder.bitcast(buffer_ptr, self.string_type)
    
        taille = ir.Constant(self.i32, 1024)
        result = self.builder.call(self.fgets, [buffer_cast, taille, file_handle])
    
        null_ptr = ir.Constant(self.string_type, None)
        est_nul = self.builder.icmp_signed('==', result, null_ptr)
    
        success_block = self.builder.append_basic_block("file_read_ok")
        error_block = self.builder.append_basic_block("file_read_error")
        continue_block = self.builder.append_basic_block("file_read_end")
    
        self.builder.cbranch(est_nul, error_block, success_block)
    
        self.builder.position_at_start(error_block)
        if clean_nom in self.variables:
            empty = self._create_string("")
            empty_ptr = self.builder.bitcast(empty, self.string_type)
            self.builder.store(empty_ptr, self.variables[clean_nom])
        self.builder.branch(continue_block)
    
        self.builder.position_at_start(success_block)
        if clean_nom in self.variables:
            self.builder.store(buffer_cast, self.variables[clean_nom])
        self.builder.branch(continue_block)
    
        self.builder.position_at_start(continue_block)
        return result


    def visitFile_open_stmt(self, ctx):
        """
        Instruction : file_open("test.txt", WRITE);
        Retourne directement le FILE* (i8*).
        """
        nom_fichier = self.visit(ctx.expression())
        mode = ctx.file_mode().getText()
    
        mode_map = {
            'READ': 'r', 'WRITE': 'w', 'APPEND': 'a',
            'READ_BIN': 'rb', 'WRITE_BIN': 'wb',
        }
        mode_str = mode_map.get(mode, 'r')
    
        mode_var = self._create_string(mode_str)
        mode_ptr = self.builder.bitcast(mode_var, self.string_type)
    
        file_handle = self.builder.call(self.fopen, [nom_fichier, mode_ptr])
    
        null_ptr = ir.Constant(self.void_ptr, None)
        est_nul = self.builder.icmp_signed('==', file_handle, null_ptr)
    
        success_block = self.builder.append_basic_block("file_open_ok")
        error_block = self.builder.append_basic_block("file_open_error")
        continue_block = self.builder.append_basic_block("file_open_end")
    
        self.builder.cbranch(est_nul, error_block, success_block)
    
        self.builder.position_at_start(error_block)
        erreur_msg = self._create_string("Erreur: Impossible d'ouvrir le fichier\n")
        erreur_ptr = self.builder.bitcast(erreur_msg, self.string_type)
        self.builder.call(self.printf, [erreur_ptr])
        self.builder.branch(continue_block)
    
        self.builder.position_at_start(success_block)
        self.builder.branch(continue_block)
    
        self.builder.position_at_start(continue_block)
    
        # Retourner DIRECTEMENT le FILE* (i8*)
        return file_handle

    # ============================================================
    # FICHIERS BINAIRES - CORRIGÉS (pas de conversion i32)
    # ============================================================

    def visitFile_read_binary_stmt(self, ctx):
        """
        file_read_bin(handle, int, variable)
        handle est déjà i8* (FILE*)
        """
        file_handle = self.visit(ctx.expression())  # Déjà i8*
        type_donnee = ctx.type_().getText()
        nom_var = ctx.ID().getText()
        clean_nom = self._clean_name(nom_var)
    
        print(f"[DEBUG] file_read_bin: type={type_donnee}, var={clean_nom}")
    
        # Allouer de l'espace pour la donnée
        llvm_type = self._get_llvm_type(type_donnee)
        ptr = self.builder.alloca(llvm_type, name=f"read_bin_{clean_nom}")
    
        # Taille en octets
        taille_octets = self._get_type_size(llvm_type)
        taille_val = ir.Constant(self.i32, taille_octets)
        count_val = ir.Constant(self.i32, 1)
        ptr_cast = self.builder.bitcast(ptr, self.void_ptr)
    
        # Appeler fread(ptr, size, 1, file) - PAS de inttoptr !
        self.builder.call(self.fread, [ptr_cast, taille_val, count_val, file_handle])
    
        # Charger la valeur lue
        valeur_lue = self.builder.load(ptr)
    
        # Stocker dans la variable
        if clean_nom in self.variables:
            self.builder.store(valeur_lue, self.variables[clean_nom])
    
        return valeur_lue


    def visitFile_write_binary_stmt(self, ctx):
        """
        file_write_bin(handle, valeur)
        handle est déjà i8* (FILE*)
        """
        file_handle = self.visit(ctx.expression(0))  # Déjà i8*
        valeur = self.visit(ctx.expression(1))
    
        print(f"[DEBUG] file_write_bin: type valeur={valeur.type}")
    
        # Allouer un espace temporaire pour la valeur
        ptr = self.builder.alloca(valeur.type, name="write_bin_tmp")
        self.builder.store(valeur, ptr)
    
        # Taille en octets
        taille_octets = self._get_type_size(valeur.type)
        taille_val = ir.Constant(self.i32, taille_octets)
        count_val = ir.Constant(self.i32, 1)
        ptr_cast = self.builder.bitcast(ptr, self.void_ptr)
    
        # Appeler fwrite(ptr, size, 1, file) - PAS de inttoptr !
        result = self.builder.call(self.fwrite, [ptr_cast, taille_val, count_val, file_handle])
    
        return result


    # ============================================================
    # EXPRESSIONS BINAIRES (dans les expressions)
    # ============================================================

    def visitFileReadBinExpr(self, ctx):
        """
        int x = file_read_bin(handle, int)
        handle est déjà i8* (FILE*)
        """
        file_handle = self.visit(ctx.expression())  # Déjà i8*
        type_donnee = ctx.type_().getText()
    
        print(f"[DEBUG] FileReadBinExpr: type={type_donnee}")
    
        # Allouer de l'espace
        llvm_type = self._get_llvm_type(type_donnee)
        ptr = self.builder.alloca(llvm_type, name="read_bin_expr")
    
        # Taille en octets
        taille_octets = self._get_type_size(llvm_type)
        taille_val = ir.Constant(self.i32, taille_octets)
        count_val = ir.Constant(self.i32, 1)
        ptr_cast = self.builder.bitcast(ptr, self.void_ptr)
    
        # Lire - PAS de inttoptr !
        self.builder.call(self.fread, [ptr_cast, taille_val, count_val, file_handle])
    
        # Retourner la valeur lue
        return self.builder.load(ptr)


    def visitFileWriteBinExpr(self, ctx):
        """
        int r = file_write_bin(handle, valeur)
        handle est déjà i8* (FILE*)
        """
        file_handle = self.visit(ctx.expression(0))  # Déjà i8*
        valeur = self.visit(ctx.expression(1))
    
        print(f"[DEBUG] FileWriteBinExpr: type={valeur.type}")
    
        # Allouer espace temporaire
        ptr = self.builder.alloca(valeur.type, name="write_bin_expr_tmp")
        self.builder.store(valeur, ptr)
    
        # Taille en octets
        taille_octets = self._get_type_size(valeur.type)
        taille_val = ir.Constant(self.i32, taille_octets)
        count_val = ir.Constant(self.i32, 1)
        ptr_cast = self.builder.bitcast(ptr, self.void_ptr)
    
        # Écrire - PAS de inttoptr !
        result = self.builder.call(self.fwrite, [ptr_cast, taille_val, count_val, file_handle])
    
        return result

    def visitFileEofExpr(self, ctx):
        """
        bool fin = file_eof(handle)
        Retourne true si fin de fichier atteinte.
        """
        file_handle = self.visit(ctx.expression())
    
        # Appeler feof(FILE*)
        result = self.builder.call(self.feof, [file_handle])
    
        # feof retourne non-zéro si EOF
        zero = ir.Constant(self.i32, 0)
        est_eof = self.builder.icmp_signed('!=', result, zero)
    
        # Convertir en i32 (bool RmLang)
        return self.builder.zext(est_eof, self.i32)

    # ============================================================
    # FONCTIONS UTILITAIRES
    # ============================================================

    def _get_type_size(self, llvm_type):
        """
        Retourne la taille en octets d'un type LLVM.
        """
        if isinstance(llvm_type, ir.IntType):
            return llvm_type.width // 8  # i8=1, i32=4, i64=8
        elif isinstance(llvm_type, ir.DoubleType):
            return 8
        elif isinstance(llvm_type, ir.FloatType):
            return 4
        elif isinstance(llvm_type, ir.PointerType):
            return 8  # Pointeur 64 bits
        else:
            return 4  # Par défaut

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