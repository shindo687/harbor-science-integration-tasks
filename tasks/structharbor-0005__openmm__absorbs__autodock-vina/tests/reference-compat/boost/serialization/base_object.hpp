#pragma once

namespace boost::serialization {
class access;

template <class T>
T& base_object(T& value) {
  return value;
}
}

