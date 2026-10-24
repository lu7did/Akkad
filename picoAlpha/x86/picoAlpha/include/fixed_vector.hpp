#pragma once
#include <array>
#include <cstddef>
#include <stdexcept>
#include <initializer_list>
#include <algorithm>
#include <utility>
// Inline, bounded storage: operations never call malloc/new. Overflow is explicit.
template<class T, std::size_t N> class FixedVector {
 std::array<T,N> storage_{}; std::size_t size_=0;
 public:
 using value_type=T;
 FixedVector()=default;
 FixedVector(std::initializer_list<T> a){for(const auto& v:a)push_back(v);}
 std::size_t size()const{return size_;}
 constexpr std::size_t capacity()const{return N;}
 bool empty()const{return size_==0;}
 void clear(){size_=0;}
 void reserve(std::size_t n){if(n>N)throw std::length_error("fixed vector capacity");}
 void resize(std::size_t n){if(n>N)throw std::length_error("fixed vector capacity");if(n>size_)std::fill(storage_.begin()+size_,storage_.begin()+n,T{});size_=n;}
 void assign(std::size_t n,const T& value){if(n>N)throw std::length_error("fixed vector capacity");std::fill_n(storage_.begin(),n,value);size_=n;}
 T& operator[](std::size_t i){return storage_[i];} const T& operator[](std::size_t i)const{return storage_[i];}
 T& front(){return storage_[0];}const T& front()const{return storage_[0];}
 T& back(){return storage_[size_-1];}const T& back()const{return storage_[size_-1];}
 T* data(){return storage_.data();}const T* data()const{return storage_.data();}
 T* begin(){return storage_.data();}const T* begin()const{return storage_.data();}
 T* end(){return storage_.data()+size_;}const T* end()const{return storage_.data()+size_;}
 void push_back(const T& value){if(size_==N)throw std::length_error("fixed vector overflow");storage_[size_++]=value;}
 void push_back(T&& value){if(size_==N)throw std::length_error("fixed vector overflow");storage_[size_++]=std::move(value);}
 template<class... Args>T& emplace_back(Args&&... args){if(size_==N)throw std::length_error("fixed vector overflow");storage_[size_]=T(std::forward<Args>(args)...);return storage_[size_++];}
 void pop_back(){if(!size_)throw std::length_error("fixed vector underflow");--size_;}
};
